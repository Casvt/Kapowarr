# Installation

The recommended way to install Kapowarr is using Docker. After installing Kapowarr, it is advised to read the [Setup After Installation page](./setup_after_installation.md).

## Docker

### Create volume or folder

Kapowarr needs some permanent place to put the database file. This can be a docker volume, or a folder on the host machine.

=== "Docker Volume"
    Both of these options will create a named volume that you can then use when launching the container.

    === "Docker CLI"
        ```bash
        docker volume create kapowarr-db
        ```

    === "Portainer"
        - Open `Volumes`
        - Click `Add Volume`
        - Enter name matching the one you'll use in compose (`kapowarr-db`, in the above example)
        - Click `Create the volume`
        - Open `Stacks`
        - Create the stack with the named volume in it.

=== "Local Folder"
    If you'd prefer to use a local folder on the host machine for storing config, Linux standards would suggest putting that in `/opt/application_name`, as the `/opt` directory is where program options should be stored.  
    In this case, you'd create the desired folder with something like `mkdir /opt/Kapowarr/db`, and replace 'kapowarr-db:/app/db' with '/opt/Kapowarr/db:/app/db'.  
    Note, the permissions on this folder need to allow the container to read, write, and execute inside it. See the [note in the FAQ](./faq.md#kapowarr-unable-to-open-database-file/) for more info.

### Launch container

Now that the database file can be stored somewhere, we can launch the container.

=== "Docker CLI"
    The command to get the docker container running can be found below:
    ```bash
    docker run -d \
        --name kapowarr \
        -v kapowarr-db:/app/db \
        -v /path/to/download_folder:/app/temp_downloads \
        -v /path/to/root_folder:/comics-1 \
        -p 5656:5656
        mrcas/kapowarr:latest
    ```

=== "Docker Compose"
    The contents of the docker-compose.yml file would look like this:
    ```yml
    version: '3.3'
    services:
        kapowarr:
            container_name: kapowarr
            volumes:
                - 'kapowarr-db:/app/db'
                - '/path/to/download_folder:/app/temp_downloads'
                - '/path/to/root_folder:/comics-1'
            ports:
                - '5656:5656'
            image: 'mrcas/kapowarr:latest'
    ```

A few important notes about the command/file before launching the container:

1. If you're using a folder on the host machine instead of a docker volume to store the database file, replace `kapowarr-db` with the path to the host folder. E.g. `/opt/Kapowarr/db:/app/db`.
2. Replace `/path/to/download_folder` with the path to your desired download folder on the host machine. Everything is downloaded to this folder and when completed, moved out of to their final destination. It's smart to set this on a disk that can sustain more writes than normal. Ideally something like a _non_-network mounted ssd, but pretty much everything will suffice.
3. Replace `/path/to/root_folder` with the path to your desired root folder on the host machine. Then, this folder will get mapped to `/comics-1` inside the docker container. When adding a root folder in Kapowarr, you'll then set it's location as `/comics-1`, mapping it this way to where ever `/path/to/root_folder` may point.
4. You can map multiple root folders by repeating `-v /path/to/root_folder:/comics-1` for the Docker CLI command or `- /path/to/root_folder:/comics-1` for the Docker Compose file, but then supplying different values for `/path/to/root_folder` and `/comics-1`. E.g. `-v /media/Comics-2:/comics-2` for the Docker CLI command or `- /media/Comics-2:/comics-2` for the Docker Compose file, then add `/comics-2` as your second root folder in Kapowarr.
5. Information on how to change the port can be found on the [Setup After Installation page](./setup_after_installation.md#port).

### Docker example

=== "Docker CLI"
    ```bash
    docker run -d \
        --name kapowarr \
        -v kapowarr-db:/app/db \
        -v /home/cas/media/Downloads:/app/temp_downloads \
        -v /home/cas/media/Comics:/comics-1 \
        -v /home/cas/other_media/Comics-2:/comics-2 \
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

In this example, we use a Docker volume as the place to store the database file, set `/home/cas/media/Downloads` as the download folder and we map the folder `/home/cas/media/Comics` to `/comics-1` and `/home/cas/other_media/Comics-2` to `/comics-2`. In Kapowarr, you'd then add `/comics-1` and `/comics-2` as root folders.

## Manual Install

Coming soon
