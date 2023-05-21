"""
This file is a stripped-down and modified version of the mega.py project.
The credits for all code below, except changes mentioned here under, go to the
original author.

LINK: https://github.com/odwyersoftware/mega.py
AUTHOR: odwyersoftware
LICENSE: Apache-2.0 license

DIFFERENCES:
	STRIPPED-DOWN:
		1. Everything put inside one file, which is this one
		2. All functions and imports removed that are not used in Kapowarr
		3. Some code was removed because it was not needed anymore (mostly
		   function arguments and variables), after stripping it down
	MODIFICATIONS:
		1. Included instance variables that are updated while downloading,
		giving info about the download like speed and progress
		2. Added functionality to stop download
		3. Changed file being downloaded to temp directory first to
		file being downloaded directly in target directory
		4. Rewritten some code to either make it more modern or reduce imports
		5. Made imports more specific
"""

from base64 import b64decode, b64encode
from binascii import hexlify, unhexlify
from codecs import latin_1_decode, latin_1_encode
from hashlib import pbkdf2_hmac
from json import dumps, loads
import logging
from math import ceil
from random import randint
from re import findall, search
from struct import pack, unpack
from time import perf_counter, time

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Util import Counter
from requests import get, post
from simplejson.errors import JSONDecodeError
from tenacity import retry, retry_if_exception_type, wait_exponential

from backend.custom_exceptions import DownloadLimitReached

_CODE_TO_DESCRIPTIONS = {
	-1: ('EINTERNAL',
		 ('An internal error has occurred. Please submit a bug report, '
		  'detailing the exact circumstances in which this error occurred')),
	-2: ('EARGS', 'You have passed invalid arguments to this command'),
	-3: ('EAGAIN',
		 ('(always at the request level) A temporary congestion or server '
		  'malfunction prevented your request from being processed. '
		  'No data was altered. Retry. Retries must be spaced with '
		  'exponential backoff')),
	-4: ('ERATELIMIT',
		 ('You have exceeded your command weight per time quota. Please '
		  'wait a few seconds, then try again (this should never happen '
		  'in sane real-life applications)')),
	-5: ('EFAILED', 'The upload failed. Please restart it from scratch'),
	-6:
	('ETOOMANY',
	 'Too many concurrent IP addresses are accessing this upload target URL'),
	-7:
	('ERANGE', ('The upload file packet is out of range or not starting and '
				'ending on a chunk boundary')),
	-8: ('EEXPIRED',
		 ('The upload target URL you are trying to access has expired. '
		  'Please request a fresh one')),
	-9: ('ENOENT', 'Object (typically, node or user) not found'),
	-10: ('ECIRCULAR', 'Circular linkage attempted'),
	-11: ('EACCESS',
		  'Access violation (e.g., trying to write to a read-only share)'),
	-12: ('EEXIST', 'Trying to create an object that already exists'),
	-13: ('EINCOMPLETE', 'Trying to access an incomplete resource'),
	-14: ('EKEY', 'A decryption operation failed (never returned by the API)'),
	-15: ('ESID', 'Invalid or expired user session, please relogin'),
	-16: ('EBLOCKED', 'User blocked'),
	-17: ('EOVERQUOTA', 'Request over quota'),
	-18: ('ETEMPUNAVAIL',
		  'Resource temporarily not available, please try again later'),
	-19: ('ETOOMANYCONNECTIONS', 'many connections on this resource'),
	-20: ('EWRITE', 'Write failed'),
	-21: ('EREAD', 'Read failed'),
	-22: ('EAPPKEY', 'Invalid application key; request not processed'),
}


class RequestError(Exception):
	"""
	Error in API request
	"""
	def __init__(self, message):
		code = message
		self.code = code
		code_desc, long_desc = _CODE_TO_DESCRIPTIONS[code]
		self.message = f'{code_desc}, {long_desc}'

	def __str__(self):
		return self.message


EMPTY_IV = b'\0' * 16

def makebyte(x):
	return latin_1_encode(x)[0]


def makestring(x):
	return latin_1_decode(x)[0]


def aes_cbc_encrypt(data, key):
	return AES.new(key, AES.MODE_CBC, EMPTY_IV).encrypt(data)


def aes_cbc_decrypt(data, key):
	return AES.new(key, AES.MODE_CBC, EMPTY_IV).decrypt(data)


def aes_cbc_encrypt_a32(data, key):
	return str_to_a32(aes_cbc_encrypt(a32_to_str(data), a32_to_str(key)))


def aes_cbc_decrypt_a32(data, key):
	return str_to_a32(aes_cbc_decrypt(a32_to_str(data), a32_to_str(key)))


def stringhash(str, aeskey):
	s32 = str_to_a32(str)
	h32 = [0, 0, 0, 0]
	for i in range(len(s32)):
		h32[i % 4] ^= s32[i]
	for r in range(0x4000):
		h32 = aes_cbc_encrypt_a32(h32, aeskey)
	return a32_to_base64((h32[0], h32[2]))


def prepare_key(arr):
	pkey = [0x93C467E3, 0x7DB0C7A4, 0xD1BE3F81, 0x0152CB56]
	for r in range(0x10000):
		for j in range(0, len(arr), 4):
			key = [0, 0, 0, 0]
			for i in range(4):
				if i + j < len(arr):
					key[i] = arr[i + j]
			pkey = aes_cbc_encrypt_a32(pkey, key)
	return pkey


def encrypt_key(a, key):
	return sum((aes_cbc_encrypt_a32(a[i:i + 4], key)
				for i in range(0, len(a), 4)), ())


def decrypt_key(a, key):
	return sum((aes_cbc_decrypt_a32(a[i:i + 4], key)
				for i in range(0, len(a), 4)), ())


def a32_to_str(a):
	return pack('>%dI' % len(a), *a)


def str_to_a32(b):
	if isinstance(b, str):
		b = makebyte(b)
	if len(b) % 4:
		# pad to multiple of 4
		b += b'\0' * (4 - len(b) % 4)
	return unpack('>%dI' % (len(b) / 4), b)


def mpi_to_int(s):
	"""
	A Multi-precision integer is encoded as a series of bytes in big-endian
	order. The first two bytes are a header which tell the number of bits in
	the integer. The rest of the bytes are the integer.
	"""
	return int(hexlify(s[2:]), 16)


def extended_gcd(a, b):
	if a == 0:
		return (b, 0, 1)
	else:
		g, y, x = extended_gcd(b % a, a)
		return (g, x - (b // a) * y, y)


def modular_inverse(a, m):
	g, x, y = extended_gcd(a, m)
	if g != 1:
		raise Exception('modular inverse does not exist')
	else:
		return x % m


def base64_url_decode(data):
	data += '=='[(2 - len(data) * 3) % 4:]
	for search, replace in (('-', '+'), ('_', '/'), (',', '')):
		data = data.replace(search, replace)
	return b64decode(data)


def base64_to_a32(s):
	return str_to_a32(base64_url_decode(s))


def base64_url_encode(data):
	data = b64encode(data)
	data = makestring(data)
	for search, replace in (('+', '-'), ('/', '_'), ('=', '')):
		data = data.replace(search, replace)
	return data


def a32_to_base64(a):
	return base64_url_encode(a32_to_str(a))


def get_chunks(size: int):
	p = 0
	s = 0x20000
	while p + s < size:
		yield s
		p += s
		if s < 0x100000:
			s += 0x20000
	yield size - p


def decrypt_attr(attr, key):
	attr = aes_cbc_decrypt(attr, a32_to_str(key))
	attr = makestring(attr)
	attr = attr.rstrip('\0')
	return loads(attr[4:]) if attr[:6] == 'MEGA{"' else False

sids = {}
class Mega:
	def __init__(self, url: str, email: str=None, password: str=None, only_check_login: bool=False):
		self.downloading: bool = False
		self.progress: float = 0.0
		self.speed: float = 0.0
		self.size: int = 0

		self.url = url
		self.schema = 'https'
		self.domain = 'mega.co.nz'
		self.timeout = 160  # max secs to wait for resp from api requests
		self.sid = None
		self.sequence_num = randint(0, 0xFFFFFFFF)

		logged_in = False
		try:
			if email is not None:
				if not email in sids or only_check_login:
					# No sid fetched for user yet
					self._login_user(email, password)
					sids.update({email: (self.sid, None)})
				self.sid = sids[email][0]
				if only_check_login:
					return
				logged_in = True
		except JSONDecodeError:
			logging.error('Login credentials for mega are invalid. Login failed.')
			raise RequestError(-16)
		if not logged_in:
			try:
				if not -1 in sids:
					# No sid fetched for user yet
					# Make it "expire" after an hour
					self.login_anonymous()
					sids.update({-1: (self.sid, time() + 3600)})
				expire_time = sids[-1][1]
				if expire_time <= time():
					# Current sid is "expired"
					self.login_anonymous()
					sids.update({-1: (self.sid, time() + 3600)})
				self.sid = sids[-1][0]
					
			except JSONDecodeError:
				raise RequestError(-16)
		
		self.file_id, file_key = self._parse_url(url).split('!')
		try:
			file_data = self._api_request({
				'a': 'g',
				'g': 1,
				'p': self.file_id
			})
		except JSONDecodeError:
			raise RequestError(-18)

		# Seems to happens sometime... When this occurs, files are
		# inaccessible also in the official also in the official web app.
		# Strangely, files can come back later.
		if not 'g' in file_data:
			raise RequestError('File not accessible anymore')

		self.size = file_data['s']

		r = get(file_data['g'], stream=True)
		r.close()
		if r.status_code == 509:
			# Download limit reached
			raise DownloadLimitReached('mega')

		file_key = base64_to_a32(file_key)
		self.k = (file_key[0] ^ file_key[4], file_key[1] ^ file_key[5],
				file_key[2] ^ file_key[6], file_key[3] ^ file_key[7])
		self.iv = file_key[4:6] + (0, 0)
		self.meta_mac = file_key[6:8]

		attribs = base64_url_decode(file_data['at'])
		attribs = decrypt_attr(attribs, self.k)
		self.mega_filename = attribs.get('n', '')

	def _login_user(self, email: str, password: str):
		logging.debug('Logging into Mega with user account')
		email = email.lower()
		get_user_salt_resp = self._api_request({'a': 'us0', 'user': email})
		user_salt = None
		try:
			user_salt = base64_to_a32(get_user_salt_resp['s'])
		except KeyError:
			# v1 user account
			password_aes = prepare_key(str_to_a32(password))
			user_hash = stringhash(email, password_aes)
		else:
			# v2 user account
			pbkdf2_key = pbkdf2_hmac(hash_name='sha512',
									password=password.encode(),
									salt=a32_to_str(user_salt),
									iterations=100000,
									dklen=32)
			password_aes = str_to_a32(pbkdf2_key[:16])
			user_hash = base64_url_encode(pbkdf2_key[-16:])
		resp = self._api_request({'a': 'us', 'user': email, 'uh': user_hash})
		if isinstance(resp, int):
			raise RequestError(resp)
		self._login_process(resp, password_aes)

	def login_anonymous(self):
		logging.debug('Logging into Mega anonymously')
		master_key = [randint(0, 0xFFFFFFFF)] * 4
		password_key = [randint(0, 0xFFFFFFFF)] * 4
		session_self_challenge = [randint(0, 0xFFFFFFFF)] * 4

		user = self._api_request({
			'a':
			'up',
			'k':
			a32_to_base64(encrypt_key(master_key, password_key)),
			'ts':
			base64_url_encode(
				a32_to_str(session_self_challenge) +
				a32_to_str(encrypt_key(session_self_challenge, master_key)))
		})

		resp = self._api_request({'a': 'us', 'user': user})
		if isinstance(resp, int):
			raise RequestError(resp)
		self._login_process(resp, password_key)

	def _login_process(self, resp, password):
		encrypted_master_key = base64_to_a32(resp['k'])
		self.master_key = decrypt_key(encrypted_master_key, password)
		if 'tsid' in resp:
			tsid = base64_url_decode(resp['tsid'])
			key_encrypted = a32_to_str(
				encrypt_key(str_to_a32(tsid[:16]), self.master_key))
			if key_encrypted == tsid[-16:]:
				self.sid = resp['tsid']
		elif 'csid' in resp:
			encrypted_rsa_private_key = base64_to_a32(resp['privk'])
			rsa_private_key = decrypt_key(encrypted_rsa_private_key,
										  self.master_key)

			private_key = a32_to_str(rsa_private_key)
			# The private_key contains 4 MPI integers concatenated together.
			rsa_private_key = [0, 0, 0, 0]
			for i in range(4):
				# An MPI integer has a 2-byte header which describes the number
				# of bits in the integer.
				bitlength = (private_key[0] * 256) + private_key[1]
				bytelength = ceil(bitlength / 8)
				# Add 2 bytes to accommodate the MPI header
				bytelength += 2
				rsa_private_key[i] = mpi_to_int(private_key[:bytelength])
				private_key = private_key[bytelength:]

			first_factor_p = rsa_private_key[0]
			second_factor_q = rsa_private_key[1]
			private_exponent_d = rsa_private_key[2]
			# In MEGA's webclient javascript, they assign [3] to a variable
			# called u, but I do not see how it corresponds to pycryptodome's
			# RSA.construct and it does not seem to be necessary.
			rsa_modulus_n = first_factor_p * second_factor_q
			phi = (first_factor_p - 1) * (second_factor_q - 1)
			public_exponent_e = modular_inverse(private_exponent_d, phi)

			rsa_components = (
				rsa_modulus_n,
				public_exponent_e,
				private_exponent_d,
				first_factor_p,
				second_factor_q,
			)
			rsa_decrypter = RSA.construct(rsa_components)

			encrypted_sid = mpi_to_int(base64_url_decode(resp['csid']))

			sid = '%x' % rsa_decrypter._decrypt(encrypted_sid)
			sid = unhexlify('0' + sid if len(sid) % 2 else sid)
			self.sid = base64_url_encode(sid[:43])

	@retry(retry=retry_if_exception_type(RuntimeError),
		   wait=wait_exponential(multiplier=2, min=2, max=60))
	def _api_request(self, data):
		params = {'id': self.sequence_num}
		self.sequence_num += 1

		if self.sid:
			params.update({'sid': self.sid})

		# ensure input data is a list
		if not isinstance(data, list):
			data = [data]

		url = f'{self.schema}://g.api.{self.domain}/cs'
		json_resp = post(
			url,
			params=params,
			data=dumps(data),
			timeout=self.timeout,
		).json()
		try:
			if isinstance(json_resp, list):
				int_resp = json_resp[0] if isinstance(json_resp[0],
													  int) else None
			elif isinstance(json_resp, int):
				int_resp = json_resp
		except IndexError:
			int_resp = None
		if int_resp is not None:
			if int_resp == 0:
				return int_resp
			if int_resp == -3:
				msg = 'Request failed, retrying'
				raise RuntimeError(msg)
			raise RequestError(int_resp)
		return json_resp[0]

	def _parse_url(self, url):
		"""Parse file id and key from url."""
		if '/file/' in url:
			# V2 URL structure
			url = url.replace(' ', '')
			file_id = findall(r'\W\w\w\w\w\w\w\w\w\W', url)[0][1:-1]
			id_index = search(file_id, url).end()
			key = url[id_index + 1:]
			return f'{file_id}!{key}'
		elif '!' in url:
			# V1 URL structure
			match = findall(r'/#!(.*)', url)
			path = match[0]
			return path
		else:
			raise RequestError('Url key missing')

	def download_url(self, filename: str):
		self.downloading = True

		url = self._api_request({
			'a': 'g',
			'g': 1,
			'p': self.file_id
		})['g']

		r = get(url, stream=True).raw
		size_downloaded = 0
		with open(filename, 'wb') as f:
			k_str = a32_to_str(self.k)
			counter = Counter.new(128,
								  initial_value=((self.iv[0] << 32) + self.iv[1]) << 64)
			aes = AES.new(k_str, AES.MODE_CTR, counter=counter)

			mac_bytes = EMPTY_IV
			mac_encryptor = AES.new(k_str, AES.MODE_CBC,
									mac_bytes)
			iv_str = a32_to_str([self.iv[0], self.iv[1], self.iv[0], self.iv[1]])

			start_time = perf_counter()
			for chunk_size in get_chunks(self.size):
				if not self.downloading:
					break

				chunk = r.read(chunk_size)
				if not chunk:
					# Download limit reached mid download
					raise DownloadLimitReached('mega')

				chunk = aes.decrypt(chunk)
				f.write(chunk)

				encryptor = AES.new(k_str, AES.MODE_CBC, iv_str)

				mv = memoryview(chunk)
				chunk_length = len(chunk)
				modchunk = chunk_length % 16
				if not modchunk:
					modchunk = 16
					last_block = chunk[-modchunk:]
				else:
					last_block = chunk[-modchunk:] + (b'\0' * (16 - modchunk))
				rest_of_chunk = mv[:-modchunk]
				
				encryptor.encrypt(rest_of_chunk)
				input_to_mac = encryptor.encrypt(last_block)
				mac_bytes = mac_encryptor.encrypt(input_to_mac)

				size_downloaded += chunk_length
				self.speed = round(chunk_length / (perf_counter() - start_time), 2)
				self.progress = round(size_downloaded / self.size * 100, 2)
				start_time = perf_counter()

		if self.downloading:
			file_mac = str_to_a32(mac_bytes)
			# check mac integrity
			if (file_mac[0] ^ file_mac[1],
					file_mac[2] ^ file_mac[3]) != self.meta_mac:
				raise ValueError('Mismatched mac')

		return
