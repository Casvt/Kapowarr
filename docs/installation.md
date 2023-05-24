# Installation

The recommended way to install Kapowarr is using Docker. After installing Kapowarr, it is advised to read the [Setup After Installation page](./setup_after_installation.md).

## Docker
=== "Docker CLI"
	The command to get the docker container running can be found below:
	```bash
	docker run -d \
		--name kapowarr \
		-v kapowarr-db:/app/db \
		-v {DOWNLOADFOLDER}:/app/temp_downloads \
		-v {ROOTFOLDER}:/content \
		-p 5656:5656
		mrcas/kapowarr:latest
	```
	A few notes about this command:

	1. Replace `{DOWNLOADFOLDER}` with the path to your desired download folder. Everything is downloaded to this folder and when completed, moved out of to their final destination. It's smart to set this on a disk that can sustain more writes than normal. Ideally something like a _non_-network mounted ssd.
	2. Replace `{ROOTFOLDER}` with the path to your desired root folder. Then, this folder will get mapped to `/content` inside the docker container. When adding a root folder in Kapowarr, you'll then set it's location as `/content`, mapping it this way to where ever `{ROOTFOLDER}` may be.
	3. You can map multiple root folders by repeating `-v {ROOTFOLDER}:/content` in the command, but then supplying different values for `{ROOTFOLDER}` and `/content`.
	4. Information on how to change the port can be found on the [Setup After Installation page](./setup_after_installation.md#port).

=== "Docker Compose"
	The contents of the docker-compose.yml file would look like this:
	```yml
	version: '3.3'
	services:
		kapowarr:
			container_name: kapowarr
			volumes:
				- 'kapowarr-db:/app/db'
				- '{DOWNLOADFOLDER}:/app/temp_downloads'
				- '{ROOTFOLDER}:/content'
			ports:
				- '5656:5656'
			image: 'mrcas/kapowarr:latest'
	```
	A few notes about this file:

	1. Replace `{DOWNLOADFOLDER}` with the path to your desired download folder. Everything is downloaded to this folder and when completed, moved out of to their final destination. It's smart to set this on a disk that can sustain more writes than normal. Ideally something like a _non_-network mounted ssd.
	2. Replace `{ROOTFOLDER}` with the path to your desired root folder. Then, this folder will get mapped to `/content` inside the docker container. When adding a root folder in Kapowarr, you'll then set it's location as `/content`, mapping it this way to where ever `{ROOTFOLDER}` may be.
	3. You can map multiple root folders by repeating `- {ROOTFOLDER}:/content` in the file, but then supplying different values for `{ROOTFOLDER}` and `/content`.
	4. Information on how to change the port can be found on the [Setup After Installation page](./setup_after_installation.md#port).

### Docker example
=== "Docker CLI"
	```bash
	docker run -d \
		--name kapowarr \
		-v kapowarr-db:/app/db \
		-v /home/cas/media/Downloads:/app/temp_downloads \
		-v /home/cas/media/Comics:/RF \
		-v /home/cas/media/Comics-2:/RF-2 \
		-p 5656:5656
		mrcas/kapowarr:latest
	```

=== "Docker Compose"
	```yml
	version: '3.3'
	services:
		kapowarr:
			container_name: kapowarr
			volumes:
				- 'kapowarr-db:/app/db'
				- '/home/cas/media/Downloads:/app/temp_downloads'
				- '/home/cas/media/Comics:/RF'
				- '/home/cas/media/Comics-2:/RF-2'
			ports:
				- '5656:5656'
			image: 'mrcas/kapowarr:latest'
	```

In this example, we set `/home/cas/media/Downloads` as the download folder and we map the folder `/home/cas/media/Comics` to `/RF` and `/home/cas/media/Comics-2` to `/RF-2`. In Kapowarr, you'd then add `/RF` and `/RF-2` as root folders.

## Manual Install
Coming soon

