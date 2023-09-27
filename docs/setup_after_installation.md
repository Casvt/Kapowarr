# Setup after installation

After installing Kapowarr, you should have access to the web-ui. Kapowarr needs some configuration in order for it to work properly.

## Port

The first thing to do is decide if you want to leave Kapowarr on the default port of 5656. If you _do_, you can go to the next step.  
If you want to _change_ the port, refer to [port](./settings.md#port-number) on the Setting page.  

## Authentication

If you want to put a password on your instance of Kapowarr, refer to [Authentication](./settings.md#security).  
_Note: If you are exposing Kapowarr to the internet, we highly recommend this._

## ComicVine API key

Kapowarr uses ComicVine as its metadata source. To fetch the metadata from ComicVine, Kapowarr needs access to the API, which requires an API key.  
See [Comic Vine API Key](./settings.md#comic-vine-api-key) on the Settings page for how to get one.  

Once you've entered your key and hit "Save", move on to Root Folders.  

## Root Folders

Root folders are the base folders that Kapowarr works in. All content is put in these folders.  
Refer to [Root Folders](./settings.md#root-folders) for more details.  
_Note: at least one of these must be set before you are able to add any volumes to monitor, as without it Kapowarr cannot know where to put the files._

## Downloading

Kapowarr's biggest feature is being able to download comics. The [Settings -> Download](./settings.md#download) section has all settings regarding the downloading.

### Download folder

The download folder is where all downloads are downloaded to, before they get moved to their final destination.  
In most cases, the default of `/app/temp_downloads` works best. If you wish to change this, refer to [Direct Download Temporary Folder](./settings.md#direct-download-temporary-folder).  

### Service preference

If you have an account with Mega, set that service as the priority and add a credential for it.  
The other services will then be used as a fallback option for if a link fails.

For a full explanation, see [Service Preference](./settings.md#service-preference).  

### Credentials

This only applies if you have an account with Mega (for now).  
Refer to [Credentials](./settings.md#credentials) for more info.

## Building up a library

Now you're ready to build a library. At Volumes -> Add Volume, you can search for volumes and add them to your library. Once you add one, a folder is automatically created for the volume in the root folder selected (see Settings -> Media Management -> File Naming -> [Volume Folder Naming](./settings.md#volume-folder-naming)). Then you can start downloading content for the volume, and all files will be put in this volume folder. The naming of the files follows the format set in the settings (see Settings -> Media Management -> [File Naming](./settings.md#file-naming)).

## Importing a library

If you have an existing library that you want to import into Kapowarr, use the "Library Import" feature found at Volumes -> Library Import. 
