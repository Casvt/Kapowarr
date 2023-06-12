# Installation

The recommended way to install Kapowarr is using Docker. After installing Kapowarr, it is advised to read the [Setup After Installation page](./setup_after_installation.md).

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

=== "Docker Compose (custom user)"
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
            environment:
                - PUID: 1000
                - PGID: 1000
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
    6. If you define a custom PUID and GUID here, they must have permission on any folder you've mapped in. The default user ID of '1000' is the first non-root user created on any Debian-based system, and generally exists on the host. If you are unsure of the _UID_ of the user you'd like the container to present as, see [Custom User](#custom-user).

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

=== "Docker Compose (custom user)"
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
            environment:
                - PUID: 1000
                - PGID: 1000
            ports:
                - '5656:5656'
            image: 'mrcas/kapowarr:latest'
    ```

In this example, we set `/home/cas/media/Downloads` as the download folder and we map the folder `/home/cas/media/Comics` to `/RF` and `/home/cas/media/Comics-2` to `/RF-2`. In Kapowarr, you'd then add `/RF` and `/RF-2` as root folders.  
We also have Kapowarr running with a user that has the user ID 1000 (the default non-root user for a linux server). If you have a user that has less permission than root that you'd like Kapowarr to run as, you'd define their user ID and group ID here.

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

### Custom User

If you want to have Kapowarr run as a user other than root (for file permissions, or security purposes), you will need the user ID.  
For a custom _group_, the same applies, but the group ID instead.  

=== "Ubuntu"
    User ID: `id -u <username>`  
    Replace '<username>' with the actual username you'd like it to run as.  
    Group ID: `id -g <username>`  
    Replace '<username>' with the actual username you'd like to find the group of.

=== "Debian"
    User ID: `id -u <username>`  
    Replace '<username>' with the actual username you'd like it to run as.  
    Group ID: `id -g <username>`  
    Replace '<username>' with the actual username you'd like to find the group of.

=== "TrueNAS"
    User ID: In the web UI, go to Credentials -> Local Users.  
    Find the relevant username you'd like to use, and look at the 'UID' column to find the UID.
    Group ID: In the web UI, go to Credentials -> Local Groups.  
    Find the relevant group you'd like to use, and look at the 'GID' column to find the GID.


## Manual Install

Coming soon
