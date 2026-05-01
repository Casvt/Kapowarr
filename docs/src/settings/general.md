## Host

This section defines how Kapowarr binds to a IP/port when starting up. Changing any setting here will make Kapowarr automatically restart after saving. Access the web-ui within 60 seconds for the changes to stay, or they will be reverted.

### Bind Address

This tells Kapowarr what IP address to bind to. Using `0.0.0.0` will have Kapowarr bind to all interfaces it finds on the host machine. You can also enter an IPv6 address.

_Note: this setting is not applicable if you have Kapowarr deployed using Docker._

### Port Number

This tells Kapowarr what port to listen on. The default is `5656`, which would put the Kapowarr UI on `http://{HOST}:5656/`.

If you have Kapowarr deployed using Docker, do not change this setting but instead follow the instructions below:

=== "Docker CLI"
    Alter the command to run the container by replacing `-p 5656:5656` with `-p {PORT}:5656`, where `{PORT}` is the desired port (e.g. `-p 8009:5656`). Run the container with the new version of the command (you will need to remove the old container if you had it running before).

=== "Docker Compose"
    Alter the file to run the container and replace `- 5656:5656` with `- {PORT}:5656`, where `{PORT}` is the desired port (e.g. `- 8009:5656`). Then re-run the container with the new version of the file.

=== "Docker Desktop"
	1. Open `Containers` and locate the `kapowarr` container in the list.
	2. Click the stop button on the right, then the delete button.
	3. Follow the [instructions for launching the container](../installation/docker.md#launch-container), starting from step 3. At step 6, set the value to the desired port. For example, if you set it to `8009`, the web-UI will then be accessible via `http://{host}:8009/`. Continue following the rest of the steps.

### Base URL

If you want to put Kapowarr behind a proxy (so you can access the web-UI via a nice URL), set a base URL (it _must_ start with a `/` character). Set it empty to disable.

To get Kapowarr running on `http://example.com/kapowarr`, you would set your reverse proxy to forward the `/kapowarr` path to the IP and port of your Kapowarr instance, and set the base URL to `/kapowarr`.

## Security

### Authentication

Require authentication to access the web-ui (and API). Set to 'None' to disable. Set to 'Password' to require a password or to 'Username And Password' to require both a username and password to get access (even though there is only one user).

!!! warning "Exposing Kapowarr"
	If you are exposing your Kapowarr instance to the internet, we highly recommend enabling authentication.

??? info "Forgetting the password"
	If you forget the username and/or password, then you'll need to reset it by manually removing it in the database of Kapowarr. You can run the command below in a terminal to clear the password. If you're running Kapowarr using Docker, then you need to run the command inside the container. In this command, it is assumed that the database of Kapowarr is located at `/app/db/Kapowarr.db`. If it is somewhere else, then change the path in the command.

	```bash
	python3 -c 'import sqlite3; sqlite3.connect("/app/db/Kapowarr.db").cursor().execute("UPDATE config SET value = "" WHERE key = "auth_password";").connection.commit()'
	```

	If you not only have a password but also a username set, then you'll have to also clear the username. You can run the command below in a terminal to clear the username. Again, if the database is located somewhere else, then change the path in the command.

	```bash
	python3 -c 'import sqlite3; sqlite3.connect("/app/db/Kapowarr.db").cursor().execute("UPDATE config SET value = "" WHERE key = "auth_username";").connection.commit()'
	```

### API Key

The API key needed to authenticate when using the [Kapowarr API](../other_docs/api.md).

## Proxy

Make Kapowarr use a proxy for all network requests. Choose the protocol used to contact the proxy and then supply the hostname/IP and port. Supply a username and password if needed. Kapowarr will test whether the proxy works once you click on 'Save'. This test could take a while, especially when it's failing.

## External Websites

### Comic Vine API Key

Kapowarr uses ComicVine as its metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to the API, which requires an API key.

1. Go to [the API page of ComicVine](https://comicvine.gamespot.com/api/).
2. If you don't have a free account at ComicVine already, sign up and once logged in, revisit the linked page.
3. You'll see your ComicVine API key, which is 40 characters long and contains the letters a-f and numbers 0-9 (e.g. `da39a3ee5e6b4b0d3255bfef95601890afd80709`).
4. Copy that API key and set it as the value in the web-UI. Don't forget to save.

### FlareSolverr Base URL

Multiple services are protected by CloudFlare. This means that if Kapowarr makes too many requests too quickly, CloudFlare will block Kapowarr. [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) is a software that can bypass this block. Kapowarr can use FlareSolverr to make requests without getting blocked. If Kapowarr experiences a CloudFlare block and it doesn't have FlareSolverr setup, it will log this. Enter the base URL of your FlareSolverr instance if you want Kapowarr to make use of it. Supply the base URL without the API prefix (`/v1`). Drop-in replacements like Byparr are also supported.

## UI

### Theme

The default theme is "Light". If you like dark mode, select "Dark".

## Logging

### Log Level

The default log level is 'Info'. This means that only things that would appear in a console (or stdout) get logged. If you are troubleshooting or want to share logs, setting this to 'Debug' will make the system log what it's doing in much more detail.  

_Note that this should be set to 'Info' when not debugging, as Kapowarr logs so much in 'Debug' mode that it could slow down operation._

### Download Logs

By clicking the button, a text file will be downloaded containing all the latest logs. This file can be used in case a large amount of logs need to be shared (as it would be impractical to paste everything in a message).
