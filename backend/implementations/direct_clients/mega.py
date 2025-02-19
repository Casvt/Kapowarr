# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from hashlib import pbkdf2_hmac
from json import JSONDecodeError, dumps, loads
from random import randint
from re import compile, search
from time import perf_counter, time
from typing import Any, Callable, Dict, Generator, List, Sequence, Tuple, Union
from zipfile import ZipFile

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from urllib3.exceptions import ProtocolError

from backend.base.custom_exceptions import (ClientNotWorking,
                                            DownloadLimitReached, LinkBroken)
from backend.base.definitions import (BaseEnum, BlocklistReason, Constants,
                                      CredentialData, CredentialSource)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.credentials import Credentials

mega_url_regex = compile(
    r"https?://(?:www\.)?mega(?:\.co)?\.nz/(?:file/(?P<ID1>[\w^_]+)#(?P<K1>[\w\-,=]+)|folder/(?P<ID2>[\w^_]+)#(?P<K2>[\w\-,=]+)/file/(?P<NID>[\w^_]+)|#!(?P<ID3>[\w^_]+)!(?P<K3>[\w\-,=]+))"
)
mega_folder_regex = compile(
    r"https?://(?:www\.)?mega(?:\.co)?\.nz/folder/(?P<ID>[\w^_]+)#(?P<KEY>[\w,\-=]+)(?:/folder/(?P<SUBDIR>[\w]+))?/?$"
)


class MegaCommands(BaseEnum):
    PRELOGIN = "us0"
    ANONYMOUS_PRELOGIN = "up"
    USER_SIGNIN = "us"
    GET_DL_URL = "g"
    LIST_FOLDER = "f"


class MegaCrypto:
    @staticmethod
    def to_bytes(
        obj: str,
        encoding: str = "utf-8",
        errors: str = "strict"
    ) -> bytes:
        try:
            return obj.encode(encoding, errors)
        except AttributeError:
            return bytes(obj, encoding)

    @staticmethod
    def to_str(
        obj: bytes,
        encoding: str = "utf-8",
        errors: str = "strict"
    ) -> str:
        try:
            return obj.decode(encoding, errors)
        except AttributeError:
            return str(obj)

    @staticmethod
    def random_key() -> int:
        return randint(0, 0xFFFFFFFF)

    @staticmethod
    def a32_to_bytes(a: Sequence[int]) -> bytes:
        result = bytearray(len(a) * 4)

        for i in range(len(a) * 4):
            result[i] = (a[i >> 2] >> (24 - (i & 3) * 8)) & 0xff

        return bytes(result)

    @staticmethod
    def bytes_to_a32(s: bytes) -> Tuple[int, ...]:
        a = [0] * ((len(s) + 3) >> 2)
        for i in range(len(s)):
            a[i >> 2] |= (s[i] << (24 - (i & 3) * 8))
        return tuple(a)

    @staticmethod
    def a32_to_base64(a: Sequence[int]) -> bytes:
        return MegaCrypto.base64_encode(MegaCrypto.a32_to_bytes(a))

    @staticmethod
    def base64_to_a32(s: str) -> Tuple[int, ...]:
        return MegaCrypto.bytes_to_a32(MegaCrypto.base64_decode(s))

    @staticmethod
    def base64_decode(data: str) -> bytes:
        result = MegaCrypto.to_bytes(data, "ascii")
        #: Add padding, we need a string with a length multiple of 4
        result += b"=" * (-len(result) % 4)
        return b64decode(result, b"-_")

    @staticmethod
    def base64_encode(data: bytes) -> bytes:
        return b64encode(data, b"-_")

    @staticmethod
    def cbc_decrypt(data: bytes, key: Sequence[int]) -> bytes:
        cipher = Cipher(
            algorithms.AES(MegaCrypto.a32_to_bytes(key)),
            modes.CBC(b"\0" * 16)
        )
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    @staticmethod
    def cbc_encrypt(data: bytes, key: Sequence[int]) -> bytes:
        cipher = Cipher(
            algorithms.AES(MegaCrypto.a32_to_bytes(key)),
            modes.CBC(b"\0" * 16)
        )
        encryptor = cipher.encryptor()
        return encryptor.update(data) + encryptor.finalize()

    @staticmethod
    def ecb_decrypt(data: bytes, key: Sequence[int]) -> bytes:
        cipher = Cipher(
            algorithms.AES(MegaCrypto.a32_to_bytes(key)),
            modes.ECB()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    @staticmethod
    def ecb_encrypt(data: bytes, key: Sequence[int]) -> bytes:
        cipher = Cipher(
            algorithms.AES(MegaCrypto.a32_to_bytes(key)),
            modes.ECB()
        )
        encryptor = cipher.encryptor()
        return encryptor.update(data) + encryptor.finalize()

    @staticmethod
    def decrypt_key(data: str, key: Sequence[int]) -> Tuple[int, ...]:
        """
        Decrypt an encrypted key ('k' member of a node)
        """
        result = MegaCrypto.base64_decode(data)
        return MegaCrypto.bytes_to_a32(MegaCrypto.ecb_decrypt(result, key))

    @staticmethod
    def encrypt_key(data: Sequence[int], key: Sequence[int]):
        """
        Encrypt a decrypted key.
        """
        result = MegaCrypto.a32_to_bytes(data)
        return MegaCrypto.bytes_to_a32(MegaCrypto.ecb_encrypt(result, key))

    @staticmethod
    def get_cipher_key(key: Sequence[int]) -> Tuple[
        Tuple[int, int, int, int],
        Tuple[int, ...],
        Tuple[int, ...]
    ]:
        """
        Construct the cipher key from the given data.
        """
        k = (
            key[0] ^ key[4],
            key[1] ^ key[5],
            key[2] ^ key[6],
            key[3] ^ key[7]
        )
        iv = (*key[4:6], 0, 0)
        meta_mac = tuple(key[6:8])

        return k, iv, meta_mac

    @staticmethod
    def decrypt_attr(data: str, key: Sequence[int]) -> Any:
        """
        Decrypt an encrypted attribute (usually 'a' or 'at' member of a node)
        """
        dec_data = MegaCrypto.base64_decode(data)
        if len(key) == 4:
            k = key
        else:
            k, iv, meta_mac = MegaCrypto.get_cipher_key(key)
        attr = MegaCrypto.cbc_decrypt(dec_data, k)

        #: Data is padded, 0-bytes must be stripped
        if attr[:6] != b'MEGA{"':
            return False

        search_result = search(rb"{.+}", attr)
        if not search_result:
            return False

        return loads(search_result.group(0))

    @staticmethod
    def get_chunks(size: int) -> Generator[Tuple[int, int], Any, None]:
        """
        Calculate chunks for a given encrypted file size.
        """
        chunk_start = 0
        chunk_size = 0x20000

        while chunk_start + chunk_size < size:
            yield chunk_start, chunk_size
            chunk_start += chunk_size
            if chunk_size < 0x100000:
                chunk_size += 0x20000

        if chunk_start < size:
            yield chunk_start, size - chunk_start

    class Checksum:
        """
        Interface for checking CBC-MAC checksum.
        """

        def __init__(self, key: Sequence[int]) -> None:
            k, iv, meta_mac = MegaCrypto.get_cipher_key(key)
            self.hash = b"\0" * 16
            self.key = MegaCrypto.a32_to_bytes(k)
            self.iv = MegaCrypto.a32_to_bytes(iv[0:2] * 2)

            self.AES = Cipher(
                algorithms.AES(self.key),
                modes.CBC(self.hash)
            ).encryptor()
            return

        def update(self, chunk: bytes) -> None:
            encryptor = Cipher(
                algorithms.AES(self.key),
                modes.CBC(self.iv)
            ).encryptor()

            hash = b''
            for j in range(0, len(chunk), 16):
                block = chunk[j: j + 16].ljust(16, b"\0")
                hash = encryptor.update(block)

            encryptor.finalize()

            self.hash = self.AES.update(hash)
            return

        def digest(self) -> Tuple[int, int]:
            """
            Return the **binary** (non-printable) CBC-MAC of the message that
            has been authenticated so far.
            """
            d = MegaCrypto.bytes_to_a32(self.hash)
            return d[0] ^ d[1], d[2] ^ d[3]


class MegaAPIClient:
    def __init__(
        self,
        sid: Union[str, None] = None,
        node_id: Union[str, None] = None
    ) -> None:
        """Prepare Mega client.

        Args:
            sid (Union[int, None], optional): User session ID.
                Defaults to None.

            node_id (Union[str, None], optional): ID of file or folder.
                Defaults to None.
        """
        self.id = MegaCrypto.random_key()
        self.sid = sid
        self.node_id = node_id
        return

    def api_request(self, **kwargs) -> Union[Dict[str, Any], int]:
        get_params: Dict[str, Any] = {"id": self.id}

        if self.sid:
            get_params["sid"] = self.sid

        if self.node_id:
            get_params["n"] = self.node_id

        with Session() as session:
            response = session.post(
                Constants.MEGA_API_URL,
                params=get_params,
                data=dumps([kwargs]),
                headers={'User-Agent': Constants.BROWSER_USERAGENT}
            ).json()

        self.id += 1

        if isinstance(response, list):
            return response[0]
        return response

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}, sid={self.sid}, node_id={self.node_id}>'


class MegaAccount:
    def __init__(
        self,
        client: MegaAPIClient,
        username: Union[str, None] = None,
        password: Union[str, None] = None
    ) -> None:
        self.client = client

        try:
            if username and password:
                self.client.sid = self._login_user(username, password)
            else:
                self.client.sid = self._login_anonymous()
        except RequestsJSONDecodeError:
            raise ClientNotWorking("Failed to login into Mega")

        return

    def __get_password_key(self, password):
        password_key = MegaCrypto.a32_to_bytes(
            [0x93C467E3, 0x7DB0C7A4, 0xD1BE3F81, 0x0152CB56]
        )
        password_a32 = MegaCrypto.bytes_to_a32(
            MegaCrypto.to_bytes(password, "utf-8")
        )
        for c in range(0x10000):
            for j in range(0, len(password_a32), 4):
                key = [0, 0, 0, 0]
                for i in range(4):
                    if i + j < len(password_a32):
                        key[i] = password_a32[i + j]
                password_key = MegaCrypto.cbc_encrypt(password_key, key)

        return MegaCrypto.bytes_to_a32(password_key)

    def __get_user_hash_v1(self, user, password_key):
        user_a32 = MegaCrypto.bytes_to_a32(
            MegaCrypto.to_bytes(user, "utf-8")
        )
        user_hash = [0, 0, 0, 0]
        for i in range(len(user_a32)):
            user_hash[i % 4] ^= user_a32[i]

        user_hash = MegaCrypto.a32_to_bytes(user_hash)
        for i in range(0x4000):
            user_hash = MegaCrypto.cbc_encrypt(user_hash, password_key)

        user_hash = MegaCrypto.bytes_to_a32(user_hash)

        return MegaCrypto.to_str(
            MegaCrypto.a32_to_base64((user_hash[0], user_hash[2])),
            "ascii"
        )

    def __mpi_to_int(self, s):
        """
        Convert GCRYMPI_FMT_PGP bignum format to integer.
        """
        return int(
            "".join(
                "{:02x}".format(s[2:][x])
                for x in range(len(s[2:]))
            ),
            16
        )

    def _login_user(self, user: str, password: str) -> str:
        LOGGER.debug('Logging into Mega with user account')
        user = user.lower()

        res = self.client.api_request(
            a=MegaCommands.PRELOGIN.value,
            user=user
        )
        if isinstance(res, int) or 'e' in res:
            raise ClientNotWorking(
                "An unexpected error occured when making contact with Mega"
            )

        if res["v"] == 1: # v1 account
            password_key = self.__get_password_key(password)
            user_hash = self.__get_user_hash_v1(user, password_key)

        elif res["v"] == 2: # v2 account
            pbkdf = pbkdf2_hmac(
                hash_name="SHA512",
                password=MegaCrypto.to_bytes(password, "utf-8"),
                salt=MegaCrypto.base64_decode(res["s"]),
                iterations=100_000,
                dklen=32
            )

            password_key = MegaCrypto.bytes_to_a32(pbkdf[:16])
            user_hash = MegaCrypto.to_str(
                MegaCrypto.base64_encode(pbkdf[16:]),
                "ascii"
            ).replace("=", "")

        else:
            raise ClientNotWorking(
                f"Mega account version not supported: {res['v']}"
            )

        return self._process_login(
            user=user,
            user_hash=user_hash,
            password_key=password_key
        )

    def _login_anonymous(self) -> str:
        LOGGER.debug('Logging into Mega anonymously')

        master_key = [MegaCrypto.random_key()] * 4
        password_key = [MegaCrypto.random_key()] * 4
        session_self_challenge = [MegaCrypto.random_key()] * 4

        res: Union[str, int] = self.client.api_request(
            a=MegaCommands.ANONYMOUS_PRELOGIN.value,
            k=MegaCrypto.to_str(MegaCrypto.a32_to_base64(
                MegaCrypto.encrypt_key(
                    master_key, password_key
                )
            )),
            ts=MegaCrypto.to_str(MegaCrypto.base64_encode(
                MegaCrypto.a32_to_bytes(session_self_challenge)
                + MegaCrypto.a32_to_bytes(
                    MegaCrypto.encrypt_key(session_self_challenge, master_key)
                )
            )).replace('=', '')
        ) # type: ignore
        if isinstance(res, int):
            raise ClientNotWorking(
                "An unexpected error occured when making contact with Mega"
            )

        return self._process_login(
            user=res,
            user_hash=None,
            password_key=password_key
        )

    def _process_login(
        self,
        user: str,
        user_hash: Union[str, None],
        password_key: Sequence[int]
    ) -> str:
        if user_hash:
            res = self.client.api_request(
                a=MegaCommands.USER_SIGNIN.value,
                user=user,
                uh=user_hash
            )

        else:
            res = self.client.api_request(
                a=MegaCommands.USER_SIGNIN.value,
                user=user
            )

        if isinstance(res, int) or 'e' in res:
            raise ClientNotWorking(
                "An unexpected error occured when making contact with Mega"
            )

        self.master_key = master_key = MegaCrypto.decrypt_key(
            res["k"],
            password_key
        )

        if "tsid" in res:
            tsid = MegaCrypto.base64_decode(res["tsid"])
            if (
                MegaCrypto.a32_to_bytes(
                    MegaCrypto.encrypt_key(
                        MegaCrypto.bytes_to_a32(tsid[:16]), master_key
                    )
                )
                == tsid[-16:]
            ):
                return res["tsid"]

        elif "csid" in res:
            privk = MegaCrypto.a32_to_bytes(
                MegaCrypto.decrypt_key(res["privk"], master_key)
            )
            rsa_private_key = [0, 0, 0, 0]

            for i in range(4):
                l = ((privk[0] * 256 + privk[1] + 7) // 8) + 2
                if l > len(privk):
                    raise ClientNotWorking(
                        "Failed to login into Mega"
                    )
                rsa_private_key[i] = self.__mpi_to_int(privk[:l])
                privk = privk[l:]

            if len(privk) >= 16:
                raise ClientNotWorking(
                    "Failed to login into Mega"
                )

            encrypted_sid = self.__mpi_to_int(
                MegaCrypto.base64_decode(res["csid"])
            )
            sid = "{:x}".format(
                pow(
                    encrypted_sid,
                    rsa_private_key[2],
                    rsa_private_key[0] * rsa_private_key[1],
                )
            )
            sid = "0" * (-len(sid) % 2) + sid
            sid = bytes([
                (int(sid[i: i + 2], 16))
                for i in range(0, len(sid), 2)
            ])
            sid = MegaCrypto.to_str(
                MegaCrypto.base64_encode(sid[:43]),
                "ascii"
            ).replace("=", "")
            return sid

        raise ClientNotWorking(
            "Failed to login into Mega"
        )


class MegaABC(ABC):
    size: int
    progress: float
    speed: float
    pure_link: str
    mega_filename: str

    @abstractmethod
    def __init__(self, download_link: str) -> None:
        ...

    @abstractmethod
    def download(
        self,
        filename: str,
        websocket_updater: Callable[[], Any]
    ) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...


class Mega(MegaABC):
    def __init__(self, download_link: str) -> None:
        self.client = MegaAPIClient()
        self.download_link = download_link
        self.__r = None

        self.downloading: bool = False
        self.progress = 0.0
        self.speed = 0.0

        self.login(self.client)

        id, key = self._parse_url(download_link)
        self.client.node_id = id
        self.__master_key = MegaCrypto.base64_to_a32(key)

        try:
            res = self.client.api_request(
                a=MegaCommands.GET_DL_URL.value,
                g=1,
                p=id,
                ssl=1
            )
            if (
                isinstance(res, int)
                or 'e' in res
                # Below seems to happens sometimes... When this occurs, files
                # are inaccessible also in the official also in the official web
                # app. Strangely, files can come back later.
                or 'g' not in res
            ):
                raise JSONDecodeError('', '', -1)

        except JSONDecodeError:
            raise ClientNotWorking(
                "The Mega download link is not found, does not exist anymore or is broken"
            )

        if res.get('tl', 0): # tl = time left
            # Download limit reached
            raise DownloadLimitReached('mega')

        attr = MegaCrypto.decrypt_attr(res["at"], self.__master_key)
        if not attr:
            raise ClientNotWorking("Decryption of Mega attributes failed")

        self.mega_filename = attr['n']
        self.size = res["s"]
        self.pure_link = res["g"]

        return

    @staticmethod
    def login(client: MegaAPIClient) -> None:
        cred = Credentials()
        for mega_cred in (
            *cred.get_from_source(CredentialSource.MEGA),
            CredentialData(
                id=-1,
                source=CredentialSource.MEGA,
                username=None,
                email='',
                password='',
                api_key=None
            )
        ):
            auth_token = (
                cred
                .auth_tokens.get(CredentialSource.MEGA, {})
                .get(mega_cred.email or '', (None, 0))
            )
            if auth_token[1] > time():
                client.sid = auth_token[0]
                break

            try:
                MegaAccount(
                    client,
                    mega_cred.email,
                    mega_cred.password
                )

            except ClientNotWorking:
                LOGGER.error(
                    'Login credentials for mega are invalid. Login failed.'
                )

            else:
                cred.auth_tokens.setdefault(CredentialSource.MEGA, {})[
                    mega_cred.email or ''
                ] = (client.sid, round(time()) + 3600)
                break

        else:
            # Failed to login with creds or anonymous
            raise ClientNotWorking("Unable to login in any way")

        return

    @staticmethod
    def _parse_url(download_link: str) -> Tuple[str, str]:
        regex_search = mega_url_regex.search(download_link)
        if not regex_search:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        groups = regex_search.groupdict()
        id = groups["ID1"] or groups["ID2"] or groups["ID3"]
        key = groups["K1"] or groups["K2"] or groups["K3"]

        if not (id and key):
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        return id, key

    def download(
        self,
        filename: str,
        websocket_updater: Callable[[], Any]
    ) -> None:
        websocket_updater()
        self.downloading = True
        size_downloaded = 0

        k, iv, meta_mac = MegaCrypto.get_cipher_key(
            self.__master_key
        )
        decryptor = Cipher(
            algorithms.AES(MegaCrypto.a32_to_bytes(k)),
            modes.CTR(MegaCrypto.a32_to_bytes(iv))
        ).decryptor()
        cbc_mac = MegaCrypto.Checksum(self.__master_key)

        start_time = perf_counter()
        with \
            open(filename, 'wb') as f, \
            Session().get(self.pure_link, stream=True).raw as r:

            self.__r = r
            for chunk_start, chunk_size in MegaCrypto.get_chunks(self.size):
                if not self.downloading:
                    break

                try:
                    chunk = r.read(chunk_size)
                except ProtocolError:
                    break

                if not chunk:
                    # Download limit reached mid download
                    raise DownloadLimitReached('mega')

                chunk = decryptor.update(chunk)
                f.write(chunk)
                cbc_mac.update(chunk)

                chunk_length = len(chunk)
                size_downloaded += chunk_length
                self.speed = round(
                    chunk_length / (perf_counter() - start_time),
                    2
                )
                self.progress = round(size_downloaded / self.size * 100, 2)
                start_time = perf_counter()
                websocket_updater()

        if self.downloading:
            if cbc_mac.digest() != meta_mac:
                raise ValueError("Mismatched mac")

        self.__r = None

        return

    def stop(self) -> None:
        self.downloading = False
        if (
            self.__r
            and self.__r._fp
            and not isinstance(self.__r._fp, str)
        ):
            self.__r._fp.fp.raw._sock.shutdown(2) # SHUT_RDWR
        return


class MegaFolder(MegaABC):
    def __init__(self, download_link: str) -> None:
        self.client = MegaAPIClient()
        self.download_link = self.pure_link = download_link

        self.downloading: bool = False
        self.__r = None
        self.progress = 0.0
        self.speed = 0.0

        Mega.login(self.client)

        id, key = self._parse_url(download_link)
        self.client.node_id = id
        master_key = MegaCrypto.base64_to_a32(key)

        try:
            res = self.client.api_request(
                a=MegaCommands.LIST_FOLDER.value,
                c=1,
                r=1,
                ca=1,
                ssl=1
            )
            if (
                isinstance(res, int)
                or 'e' in res
            ):
                raise JSONDecodeError('', '', -1)

        except JSONDecodeError:
            raise ClientNotWorking(
                "The Mega Folder download link is not found, does not exist anymore or is broken"
            )

        self.files: List[Dict[str, Any]] = []
        self.mega_filename = ""
        self.size = 0
        for node in res['f']:
            if node['t'] == 1:
                self.mega_filename = MegaCrypto.decrypt_attr(
                    node["a"],
                    MegaCrypto.decrypt_key(
                        node["k"].split(":")[1],
                        master_key
                    )
                )['n'] + '.zip'

            elif node['t'] == 0 and ":" in node["k"]:
                node_key = MegaCrypto.decrypt_key(
                    node["k"].split(":")[1],
                    master_key
                )
                self.files.append({
                    "node_id": node["h"],
                    "size": node["s"],
                    "name": MegaCrypto.decrypt_attr(node["a"], node_key)["n"],
                    "key": node_key
                })
                self.size += node["s"]
        return

    @staticmethod
    def _parse_url(folder_link: str) -> Tuple[str, str]:
        regex_search = mega_folder_regex.search(folder_link)
        if not regex_search:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        groups = regex_search.groupdict()
        id = groups["ID"]
        key = groups["KEY"]

        if not (id and key):
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        return id, key

    def download(
        self,
        filename: str,
        websocket_updater: Callable[[], Any]
    ) -> None:
        websocket_updater()
        self.downloading = True
        size_downloaded = 0

        with ZipFile(filename, 'w') as zip:
            for file in self.files:
                k, iv, meta_mac = MegaCrypto.get_cipher_key(
                    file["key"]
                )
                decryptor = Cipher(
                    algorithms.AES(MegaCrypto.a32_to_bytes(k)),
                    modes.CTR(MegaCrypto.a32_to_bytes(iv))
                ).decryptor()
                cbc_mac = MegaCrypto.Checksum(file["key"])

                try:
                    res = self.client.api_request(
                        a=MegaCommands.GET_DL_URL.value,
                        g=1,
                        n=file["node_id"],
                        ssl=1
                    )
                    if (
                        isinstance(res, int)
                        or 'e' in res
                        # Below seems to happens sometimes... When this occurs, files
                        # are inaccessible also in the official also in the official web
                        # app. Strangely, files can come back later.
                        or 'g' not in res
                    ):
                        raise JSONDecodeError('', '', -1)

                except JSONDecodeError:
                    raise ClientNotWorking(
                        "The Mega download link is not found, does not exist anymore or is broken"
                    )

                if res.get('tl', 0): # tl = time left
                    # Download limit reached
                    raise DownloadLimitReached('mega')

                self.pure_link = res['g']
                start_time = perf_counter()
                with \
                    zip.open(file["name"], "w", force_zip64=True) as f, \
                    Session().get(self.pure_link, stream=True).raw as r:

                    self.__r = r
                    for chunk_start, chunk_size in MegaCrypto.get_chunks(
                        file["size"]
                    ):
                        if not self.downloading:
                            break

                        try:
                            chunk = r.read(chunk_size)
                        except ProtocolError:
                            break

                        if not chunk:
                            # Download limit reached mid download
                            raise DownloadLimitReached('mega')

                        chunk = decryptor.update(chunk)
                        f.write(chunk)
                        cbc_mac.update(chunk)

                        chunk_length = len(chunk)
                        size_downloaded += chunk_length
                        self.speed = round(
                            chunk_length / (perf_counter() - start_time),
                            2
                        )
                        self.progress = round(
                            size_downloaded / self.size * 100, 2)
                        start_time = perf_counter()
                        websocket_updater()

                if self.downloading:
                    if cbc_mac.digest() != meta_mac:
                        raise ValueError("Mismatched mac")
                else:
                    break

        self.__r = None

        return

    def stop(self) -> None:
        self.downloading = False
        if (
            self.__r
            and self.__r._fp
            and not isinstance(self.__r._fp, str)
        ):
            self.__r._fp.fp.raw._sock.shutdown(2) # SHUT_RDWR
        return
