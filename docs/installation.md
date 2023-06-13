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
=== "Ubuntu"
	We can install by cloning the github code to a local directory and then running.  
	
	### Pre-requisites
	Before we can install, we need to make sure we have python3 and pip installed.

	We can check the version of Python that is currently installed by using:
	```bash
	python --version
	```
	If you have more than one version of python installed, you may need to use:
	```bash
	python3 --version
	```
	If the version is not 3.7 or above, we can install version 3.8 using the deadsnakes PPA as follows:
	```bash
	sudo apt-get install software-properties-common
	sudo add-apt-repository ppa:deadsnakes/ppa
	sudo apt-get update
	sudo apt-get install python3.8
	```
	Now we just want to make sure we have pip installed for python3:
	```bash
	sudo apt-get install python3-pip
	```

	### Installing Kapowarr
	First of all, we need to clone the git repository:
	```bash
	git clone https://github.com/Casvt/Kapowarr /opt/Kapowarr
	```
	Then we need to install the requirements:
	```bash
	pip3 install -r requirements.txt
	```
	Now, we can run the application by using
	```bash
	python3 /opt/Kapowarr/Kapowarr.py
	```
	note: If you have to run the pip command with sudo, you will need to run the python3 command with sudo as well

	By default the application listens on port 5656 - so you can go to http://localhost:5656 to start using it.  To stop the application, just hit ctrl-c

	### Setting the application to run as a service
	If you want Kapowarr to run as an application, we can set it up as follows:
	```bash
	sudo nano Kapowarr.sh
	```
	In the file editor, enter the following:
	```bash
	#!/bin/sh

	### BEGIN INIT INFO
	# Provides:          Kapowarr
	# Required-Start:    $remote_fs $syslog
	# Required-Stop:     $remote_fs $syslog
	# Default-Start:     2 3 4 5
	# Default-Stop:      0 1 6
	# Short-Description: Put a short description of the service here
	# Description:       Put a long description of the service here
	### END INIT INFO

	# Change the next 3 lines to suit where you install your script and what you want to call it
	DIR=/opt/Kapowarr
	DAEMON=/usr/bin/python3 $DIR/Kapowarr.py
	DAEMON_NAME=Kapowarr

	# Add any command line options for your daemon here
	DAEMON_OPTS=""

	# This next line determines what user the script runs as.
	# Root generally not recommended but necessary if you are using the Raspberry Pi GPIO from Python.
	DAEMON_USER=pi

	# The process ID of the script when it runs is stored here:
	PIDFILE=/var/run/$DAEMON_NAME.pid

	. /lib/lsb/init-functions

	do_start () {
		log_daemon_msg "Starting system $DAEMON_NAME daemon"
		start-stop-daemon --start --background --pidfile $PIDFILE --make-pidfile --user $DAEMON_USER --chuid $DAEMON_USER --startas $DAEMON -- $DAEMON_OPTS
		log_end_msg $?
	}
	do_stop () {
		log_daemon_msg "Stopping system $DAEMON_NAME daemon"
		start-stop-daemon --stop --pidfile $PIDFILE --retry 10
		log_end_msg $?
	}

	case "$1" in

		start|stop)
			do_${1}
			;;

		restart|reload|force-reload)
			do_stop
			do_start
			;;

		status)
			status_of_proc "$DAEMON_NAME" "$DAEMON" && exit 0 || exit $?
			;;

		*)
			echo "Usage: /etc/init.d/$DAEMON_NAME {start|stop|restart|status}"
			exit 1
			;;

	esac
	exit 0
	```
	To close and save the file, press ctrl-x, then y and enter.

	Now we just move this file to the init.d folder, make it executable and enable it as a service:
	```bash
	sudo mv Kapowarr.sh /etc/init.d/Kapowarr.sh
	sudo chmod 755 /etc/init.d/Kapowarr.sh
	sudo update-rc.d Kapowarr.sh defaults
	```
	Then we should be able to start and stop the application with:
	```bash
	sudo systemctl start Kapowarr.service
	```
	and 
	```bash
	sudo systemctl stop Kapowarr.service
	```
=== "Others"
	Coming soon

