# Setup after installation

After installing Kapowarr, you should have access to the web-ui. Kapowarr needs some configuration in order for it to work properly.

## Port

The first thing to do is decide if you want to leave Kapowarr on the default port of 5656. If you _do_, you can go to the next step. If you want to _change_ the port, continue reading.

=== "Docker CLI"
    Alter the command to run the container and replace `-p 5656:5656` with `-p {PORT}:5656`, where `{PORT}` is the desired port (e.g. `-p 8009:5656`). Then run the container with the new version of the command.

=== "Docker Compose"
    Alter the file to run the container and replace `- 5656:5656` with `- {PORT}:5656`, where `{PORT}` is the desired port (e.g. `- 8009:5656`). Then run the container with the new version of the file.

=== "Manual Install"
    Edit the port number at Settings -> General -> Host -> Port Number in the web-ui and change the value to the desired port. Then, restart Kapowarr.

## Authentication

You might want to set a password to restrict access to the web-ui (and API). Setting a password is optional. A password can be set at Settings -> General -> Security -> Login Password. Don't forget to save. From then on, it is required to enter a password in order to gain access to the web-ui (and the API). If you want to disable the password, set an empty value for the setting and save.

## ComicVine API key

Kapowarr uses ComicVine as it's metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to the API, which requires an API key.

1. Go to [the API page of ComicVine](https://comicvine.gamespot.com/api/).
2. If you don't have a free account at ComicVine already, sign up and once logged in, revisit the linked page.
3. You'll see your ComicVine API key, which is 40 characters long and contains the letters a-f and numbers 0-9 (e.g. `da39a3ee5e6b4b0d3255bfef95601890afd80709`).
4. Copy that API key and enter it as the value of Settings -> General -> Comic Vine API -> Comic Vine API Key in the web-ui. Don't forget to save.

On the documentation page about [rate limiting](./rate_limiting.md), information can be found about the handling of the ComicVine API rate limit.

## Root Folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders. When adding a volume (or when editing one), you choose in which root folder all content for that volume is put. Kapowarr will never touch any files outside the root folders (except in the [download folder](#download-folder)). You might have multiple root folders because you store your comics on multiple drives or want different access rights to certain volumes, to name a few reasons.

Root folders can be added at Settings -> Media Management -> Root Folders. Note: If you use docker to run Kapowarr and have followed the example given in the [installation instructions](./installation.md#docker), this is where you would enter `/content`, `/content2`, `/RF`, `/RF2`, etc.

## Downloading

One of Kapowarr's biggest features is being able to download comics. The Settings -> Download section has all settings regarding the downloading.

### Download folder

The download folder (Settings -> Download -> Download Location -> Direct Download Temporary Folder) is where all downloads are downloaded to, before they get moved to their final destination. If you run Kapowarr using Docker, leave this setting to it's default value of `/app/temp_downloads` and instead change the value of `/path/to/download_folder` in the Docker command ([reference](./installation.md#docker)). If you have a manual install, you can change this value to whatever you want. It is allowed to be outside your root folders.

### Service preference

Kapowarr has the ability to download directly from servers, but also to download from services like MediaFire and Mega. Websites like getcomics.org offer the same download via multiple services (multiple download links to download the same file, via different services). This settings determines what preference you have for each service. If multiple services are offered for the same download, Kapowarr will use this preference list to determine what service to pick (if the link of the top service doesn't work, Kapowarr falls back to the other options, in order). If you have an account for one of these services (see [Credentials](#credentials) setting), you might want to put that one at the top, to make Kapowarr take advantage of the extra features that the account offers (extra bandwidth, higher rate limit, etc.).

### Credentials

Kapowarr has the ability to download from services like MediaFire and Mega. These services apply limits to how much you can download per day, or a download speed limit. An (paid) account for one of these services often offers higher limits. Kapowarr can take advantage of these extra features that these accounts offer. Under the credentials section, you can add credentials of accounts, which Kapowarr will use when downloading, taking advantage of the extra features. 

## Building up a library

Now you're ready to build a library. At Volumes -> Add Volume, you can search for volumes and add them to your library.  
Once you add one, a folder is automatically created for the volume in the root folder selected (see Settings -> Media Management -> File Naming -> Volume Folder Naming).  
Then you can start downloading content for the volume, and all files will be put in this volume folder.  
The naming of the files follows the format set in the settings (see Settings -> Media Management -> File Naming).

## Importing a library

Importing an already existing library into Kapowarr is currently not very fluid (the "Library Import" feature found in Radarr/Sonarr is not yet implemented in Kapowarr).  
The currently advised way to get Kapowarr working with your current library:

1. Move all current media into the root folder, where each volume has their own folder.
2. Add a volume in Kapowarr and while adding, set the "Volume Folder" to the folder of the volume from step 1.
3. Go to the volume in Kapowarr and click the "Refresh & Scan" button. Kapowarr will scan the volume folder and import all files.
4. Refresh the web-ui.
5. (Optional) Click "Preview Rename" and Kapowarr will immediately propose new naming for the files, following the file naming format set in the settings.
6. Repeat for all volumes that you have in your current library.

There are plans to add support for the "Library Import" feature, to make the process of importing an existing library easier.
