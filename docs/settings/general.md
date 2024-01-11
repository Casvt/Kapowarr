## General

### Host

This section defines how Kapowarr binds to a port/IP when starting up.  
Any setting here requires you restart Kapowarr after saving it for it to apply.

#### Bind Address

This tells Kapowarr what IP to bind to. If you specify an IP that is _not_ on the machine running Kapowarr, you _will_ encounter errors.  
Using `0.0.0.0` will have Kapowarr bind to all interfaces it finds on the host machine.

_Note: this setting is not applicable if you have Kapowarr deployed with Docker._

#### Port Number

This tells Kapowarr what port to listen on. The default is `5656`, which would put the Kapowarr UI on `http://ip.of.host.machine:5656/`.  
If you wish to change the port, it can be changed here.  
_Note: this setting is not applicable if you have Kapowarr deployed with Docker. This should be done by following the examples below_.

=== "Docker CLI"
    Alter the command to run the container and replace `-p 5656:5656` with `-p {PORT}:5656`, where `{PORT}` is the desired port (e.g. `-p 8009:5656`).  
    Run the container with the new version of the command (you will need to remove the old container if you had it running before).

=== "Docker Compose"
    Alter the file to run the container and replace `- 5656:5656` with `- {PORT}:5656`, where `{PORT}` is the desired port (e.g. `- 8009:5656`).  
    Then re-run the container with the new version of the file.

=== "Manual Install"
    Edit the port number here by changing the value to the desired port. Press save, then restart Kapowarr.

#### Base URL

This is use for reverse proxy support - the default is empty.  
If you want to put Kapowarr behind a proxy (so you can access via a nice URL), set a Base URL (it _must_ start with a `/` character).  

To get `http://example.com/kapowarr`, you would set your reverse proxy to forward the `/kapowarr` path to the IP and port of your Kapowarr instance, and set Base URL to `/kapowarr`.

### Security

#### Login Password

You might want to set a password to restrict access to the web-ui (and API). This is optional (but highly recommended if you are exposing Kapowarr to the internet).  
From then on, it is required to enter a password in order to gain access to the web-ui (and the API).  
If you want to disable the password, set an empty value for the setting and save.

#### API Key

This is where Kapowarr defines the API key for any queries made to the [Kapowarr API](api.md).  
Documentation for the API itself will be coming in due course.

### Comic Vine API Key

Kapowarr uses ComicVine as its metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to the API, which requires an API key.

1. Go to [the API page of ComicVine](https://comicvine.gamespot.com/api/).
2. If you don't have a free account at ComicVine already, sign up and once logged in, revisit the linked page.
3. You'll see your ComicVine API key, which is 40 characters long and contains the letters a-f and numbers 0-9 (e.g. `da39a3ee5e6b4b0d3255bfef95601890afd80709`).
4. Copy that API key and enter it as the value of Settings -> General -> Comic Vine API -> Comic Vine API Key in the web-ui. Don't forget to save.

On the documentation page about [rate limiting](rate_limiting.md), information can be found about the handling of the ComicVine API rate limit.

### UI

#### Theme

The default theme is "Light". If you like dark mode, select "Dark".

### Logging

#### Log Level

The default log level is 'Info'. This means that only things that would appear in a console (or stdout) get logged.  
If troubleshooting, setting this to 'Debug' will make the system log what it's doing in much more detail.  

_Note that this should be set to 'Info' when not debugging, as the log files can start to get rather large._
