# Installation

The recommended way to install Kapowarr is using Docker. After installing Kapowarr, it is advised to read the [Setup After Installation page](../setup_after_installation).

## Docker

=== "Docker CLI"
    The command to get the docker container running can be found below:
    ```bash
    docker run -d \
        --name kapowarr \
        -v kapowarr-db:/app/db \
        -v /path/to/download_folder:/app/temp_downloads \
        -v /path/to/root_folder:/content \
        -p 5656:5656
        mrcas/kapowarr:latest
    ```
    A few notes about this command:

    1. Replace `/path/to/download_folder` with the path to your desired download folder. Everything is downloaded to this folder and when completed, moved out of to their final destination. It's smart to set this on a disk that can sustain more writes than normal. Ideally something like a _non_-network mounted ssd.
    2. Replace `/path/to/root_folder` with the path to your desired root folder. Then, this folder will get mapped to `/content` inside the docker container. When adding a root folder in Kapowarr, you'll then set it's location as `/content`, mapping it this way to where ever `/path/to/root_folder` may be.
    3. You can map multiple root folders by repeating `-v /path/to/root_folder:/content` in the command, but then supplying different values for `/path/to/root_folder` and `/content`.
    4. Information on how to change the port can be found on the [Setup After Installation page](./setup_after_installation.md#port).
    5. Using a named volume in docker requires you to create the volume before you can use it (refer to [Named Volumes](#named-volumes)).

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
                - '/path/to/root_folder:/content'
            ports:
                - '5656:5656'
            image: 'mrcas/kapowarr:latest'
    ```
    A few notes about this file:

    1. Replace `/path/to/download_folder` with the path to your desired download folder. Everything is downloaded to this folder and when completed, moved out of to their final destination. It's smart to set this on a disk that can sustain more writes than normal. Ideally something like a _non_-network mounted ssd.
    2. Replace `/path/to/root_folder` with the path to your desired root folder. Then, this folder will get mapped to `/content` inside the docker container. When adding a root folder in Kapowarr, you'll then set it's location as `/content`, mapping it this way to where ever `/path/to/root_folder` may be.
    3. You can map multiple root folders by repeating `- /path/to/root_folder:/content` in the file, but then supplying different values for `/path/to/root_folder` and `/content`.
    4. Information on how to change the port can be found on the [Setup After Installation page](./setup_after_installation.md#port).
    5. Using a named volume in docker requires you to create the volume before you can use it (refer to [Named Volumes](#named-volumes))

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

    In this example, we set `/home/cas/media/Downloads` as the download folder and we map the folder `/home/cas/media/Comics` to `/RF` and `/home/cas/media/Comics-2` to `/RF-2`. In Kapowarr, you'd then add `/RF` and `/RF-2` as root folders.

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

### Named volumes

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

Both of these options will create a named volume that you can then use in the examples above.  
If you'd prefer to use a local folder on the host machine for storing config, Linux standards would suggest putting that in `/opt/application_name`, as the `/opt` directory is where program options should be stored.  
In this case, you'd create the desired folder with something like `mkdir /opt/kapowarr/db`, and replace 'kapowarr-db:/app/db' with '/opt/kapowarr/db:/app/db'.  
Note, the permissions on this folder need to allow the container to read, write, and execute inside it. See the [note in the FAQ](../faq/#kapowarr-unable-to-open-database-file/) for more info.

## Manual Install

Coming soon
