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

=== "Windows"
    On Windows, there are a couple of extra steps involved.  

    1. [Download and install Python](https://www.python.org/downloads/). This is the framework Kapowarr runs on top of.  
       _Make sure you select to add Python to PATH when prompted. This will make installing requirements much easier._
    2. Download (or clone) the [latest Kapowarr release](https://github.com/Casvt/Kapowarr/releases/latest).  
    3. Extract the zip file to a folder on your machine.  
       We suggest something straightforward - `C:\services\Kapowarr` is what we'll use as an example.
    4. Install the required python modules (found in `requirements.txt`).
       This can be achieved from a command prompt, by changing to the folder you've extracted Kapowarr to and running a python command.
       ```
       cd C:\services\Kapowarr
       python -m pip install -r requirements.txt
       ```
    5. Run Kapowarr with the command `python C:\services\Kapowarr\kapowarr.py`.
    6. Access Kapowarr with the IP of the host machine and port 5656.  
       If it's the machine you're using, try [http://localhost:5656](http://localhost:5656)
    
    If you want Kapowarr to run in the background, without you having to start it each time your machine restarts, a tool called [nssm](https://nssm.cc/download) will allow you to configure Kapowarr to run as a system service. It is recommended that you set it up as above before doing this, as it will allow you to see any errors you may encounter on screen (instead of having nssm intercept them).

=== "Ubuntu"
    _Coming soon._

=== "macOS"
    Use docker.  
    Permissions on macOS (and GateKeeper) make this needlessly complex.  
