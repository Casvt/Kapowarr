Installing Kapowarr can be done via Docker or via a manual install. Docker requires less setup and has better support, but if your OS/system does not support Docker, you can also install Kapowarr directly on your OS via a manual install.

!!! success "Recommended Installation"
    The recommended way to install Kapowarr is using Docker.

For instructions on installing Kapowarr using Docker, see the [Docker installation instructions](./docker.md). For instructions on installing Kapowarr via a manual install, see the [manual installation instructions](./manual_install.md).

After installing Kapowarr, there is some setup needed so that Kapowarr can start doing it's job, work optimally and act to your preferences. It's advised to visit the [Setup After Installation page](./setup_after_installation.md) after installation for more information.

Updating an installation can also be found on the installation pages of the respective installation method.

## Quick Instructions

If you already have experience with Docker and the *arr suite of apps, then below you can find some quick instructions to get Kapowarr up and running fast. If you need some more guidance, follow the full guide for [Docker](./docker.md) or [a manual install](./manual_install.md).

You need to have a download folder and root folder created on the host. The database will be stored in a Docker volume. Replace the paths (`/path/to/...`) with their respective values. Add the mapped folder as your root folder in Kapowarr (`/comics-1`). See the [examples](./docker.md#example) for some extra help.

=== "Docker CLI"
	=== "Linux"

		```bash
		docker run -d \
			--name kapowarr \
			-v "kapowarr-db:/app/db" \
			-v "/path/to/download_folder:/app/temp_downloads" \
			-v "/path/to/root_folder:/comics-1" \
			-p 5656:5656 \
			mrcas/kapowarr:latest
		```

	=== "MacOS"

		```bash
		docker run -d \
			--name kapowarr \
			-v "kapowarr-db:/app/db" \
			-v "/path/to/download_folder:/app/temp_downloads" \
			-v "/path/to/root_folder:/comics-1" \
			-p 5656:5656 \
			mrcas/kapowarr:latest
		```

	=== "Windows"

		```powershell
		docker run -d --name kapowarr -v "kapowarr-db:/app/db" -v "DRIVE:\with\download_folder:/app/temp_downloads" -v "DRIVE:\with\root_folder:/comics-1" -p 5656:5656 mrcas/kapowarr:latest
		```

=== "Docker Compose"

	```yml
	version: "3.3"
	services:
	  kapowarr:
	    container_name: kapowarr
	    image: mrcas/kapowarr:latest
	    volumes:
	      - "kapowarr-db:/app/db"
	      - "/path/to/download_folder:/app/temp_downloads"
	      - "/path/to/root_folder:/comics-1"
	    ports:
	      - 5656:5656

	volumes:
	  kapowarr-db:
	```
