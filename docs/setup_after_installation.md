# Setup after installation

After installing Kapowarr, you should have access to the web-ui. Kapowarr needs some configuration in order for it to work properly.

## Port

The first thing to do is decide if you want to leave Kapowarr on the default port of 5656. If you _do_, you can go to the next step.  
If you want to _change_ the port, refer to [port](../settings/#port-number) on the Setting page.  

## Authentication

If you want to put a password on your instance of Kapowarr, refer to [Authentication](../settings/#security).  
_Note: If you are exposing Kapowarr to the internet, we highly recommend this._

## ComicVine API key

Kapowarr uses ComicVine as its metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to the API, which requires an API key.  
See [Comic Vine API Key](../settings/#comic-vine-api-key) on the Settings page for how to get one.  

Once you've entered your key and hit "Save", move on to Root Folders.  

## Root Folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders.  
Refer to [Root Folders](../settings/#root-folders) for more details.  
_Note: at least one of these must be set before you are able to add any volumes to monitor, as without it Kapowarr cannot know where to put the files._

## Downloading

Kapowarr's biggest feature is being able to download comics. The [Settings -> Download](../settings/#download) section has all settings regarding the downloading.

### Download folder

The download folder is where all downloads are downloaded to, before they get moved to their final destination.  
In most cases, the default of `/app/temp_downloads` works best. If you wish to change this, refer to [Direct Download Temporary Folder](../settings/#direct-download-temporary-folder).  

### Service preference

Kapowarr has the ability to download directly from servers, but also to download from services like MediaFire and Mega. Websites like getcomics.org offer the same download via multiple services (multiple download links to download the same file, via different services). This settings determines what preference you have for each service. If multiple services are offered for the same download, Kapowarr will use this preference list to determine what service to pick (if the link of the top service doesn't work, Kapowarr falls back to the other options, in order). If you have an account for one of these services (see [Credentials](#credentials) setting), you might want to put that one at the top, to make Kapowarr take advantage of the extra features that the account offers (extra bandwidth, higher rate limit, etc.).

### Credentials

Kapowarr has the ability to download from services like MediaFire and Mega. These services apply limits to how much you can download per day, or a download speed limit. An (paid) account for one of these services often offers higher limits. Kapowarr can take advantage of these extra features that these accounts offer. Under the credentials section, you can add credentials of accounts, which Kapowarr will use when downloading, taking advantage of the extra features.

## Building up a library

Now you're ready to build a library.  
At Volumes -> Add Volume, you can search for volumes and add them to your library.  
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
