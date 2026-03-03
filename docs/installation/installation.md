# Installation and Updating

## Installation Method

Kapowarr supports multiple installation methods. The two most common methods are using Docker and directly on your computer. The recommended method is Docker. Choose an installation method:

<div class="button-container">
	<a href="../docker">Docker</a>
	<a href="../manual_install">Manual Install</a>
</div>

After installing Kapowarr, there is some configuration needed so that it can start working and act to your preferences. It's advised to visit the [Setup After Installation page](./setup_after_installation.md) after installation for more information.

Instructions on how to update an installation can be found on the pages of the respective installation method.

## Quick Instructions

If you already have experience with Docker and the *arr suite of apps, then below you can find some quick instructions to get Kapowarr up and running fast. If you need some more guidance, follow the full guide for [Docker](./docker.md) or a [manual install](./manual_install.md).

You need to have a download folder and root folder created on the host. The database will be stored in a Docker volume. Replace the paths (`/path/to/...`) with their respective values. Set the timezone. Change the user and group the container runs as if desired. Add the mapped folder as your root folder in Kapowarr (`/comics`). See the [examples](./docker.md#example) for some extra help.

=== "Docker CLI"
	=== "Linux"

		```bash
		docker run -d \
			--name kapowarr \
			-v "kapowarr-db:/app/db" \
			-v "/path/to/download_folder:/app/temp_downloads" \
			-v "/path/to/root_folder:/comics" \
			-p 5656:5656 \
			-e PUID=0 \
			-e PGID=0 \
			-e TZ=Etc/UTC \
			mrcas/kapowarr:latest
		```

	=== "MacOS"

		```bash
		docker run -d \
			--name kapowarr \
			-v "kapowarr-db:/app/db" \
			-v "/path/to/download_folder:/app/temp_downloads" \
			-v "/path/to/root_folder:/comics" \
			-p 5656:5656 \
			-e PUID=0 \
			-e PGID=0 \
			-e TZ=Etc/UTC \
			mrcas/kapowarr:latest
		```

	=== "Windows"

		```powershell
		docker run -d --name kapowarr -v "kapowarr-db:/app/db" -v "DRIVE:\with\download_folder:/app/temp_downloads" -v "DRIVE:\with\root_folder:/comics" -p 5656:5656 -e PUID=0 -e PGID=0 -e TZ=Etc/UTC mrcas/kapowarr:latest
		```

=== "Docker Compose"

	```yml
	services:
		kapowarr:
			container_name: kapowarr
			image: mrcas/kapowarr:latest
			environment:
				- PUID=0
				- PGID=0
				- TZ=Etc/UTC
			volumes:
				- "kapowarr-db:/app/db"
				- "/path/to/download_folder:/app/temp_downloads"
				- "/path/to/comics:/comics"
			ports:
				- 5656:5656

	volumes:
		kapowarr-db:
	```