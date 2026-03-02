---
hide:
  - navigation
---

# FAQ

## Project

??? question "Does Kapowarr support XYZ?"
    ### Does Kapowarr support XYZ?

    Look around in the web-UI and this documentation hub first, to see if you find it. Otherwise you can ask on the [Discord server](https://discord.gg/5gWtW3ekgZ). If you are sure that it is not available in Kapowarr, you can make an issue on GitHub to request it.

??? question "When will XYZ be added?"
    ### When will XYZ be added?

    First, check out the [project board](https://github.com/users/Casvt/projects/5) to see if it's already on there and if so, at what stage it is. If it's not, check if a feature request is already made for it on the [issues page](https://github.com/Casvt/Kapowarr/issues) and otherwise make one.

??? question "What are the alpha releases?"
    ### What are the alpha releases?

    Sometimes, between stable releases, alpha releases are published. These releases contain new features and/or fixes that need to be tested before being published to the general public. So they contain the latest features and fixes, but possibly also bugs. Once any problems found in the alpha releases are fixed, the stable changes are released in a stable release. The alpha releases can be used by pulling the Docker image from the [`mrcas/kapowarr-alpha`](https://hub.docker.com/r/mrcas/kapowarr-alpha) repository. Any stable releases are also published in the alpha repository, so you do not have to switch to the stable repository in order to get the stable releases.

## Hosting

??? question "Why is the binding address set to 0.0.0.0?"
    ### Why is the binding address set to 0.0.0.0?

    This is the default value, and will make Kapowarr bind to all interfaces it finds on the host machine. You can specify a specific IP address that the host machine owns to only bind to, but this is uncommon.

??? question "How do I access the web-UI?"
    ### How do I access the web-UI?

    - **Localhost**  
        If you want to access the web-UI from the same computer that Kapowarr is running on, you can go to [http://localhost:5656](http://localhost:5656). This is assuming that Kapowarr is running on the default port of 5656.

    - **IP**  
        You can access the web-UI from any computer that is on the same network by using the IP address of the computer that Kapowarr is running on. Then you can access it via `{IP}:5656`. So if the IP address is `192.168.2.15`, you can access the web-UI via `192.168.2.15:5656` or `http://192.168.2.15:5656`.

    - **Hostname**  
        You can access the web-UI in the same way that you can access it using the IP address, but by using the hostname of the computer instead (if the computer has a hostname). For example, if your computer has the hostname `my-server`, then you can access the web--UI via `my-server:5656` or `http://my-server:5656`.

    !!! tip "Check your firewall"
        If you can still not access the web-UI, check if the port is allowed through the firewall.

## Library Management

??? question "Why can't I add volumes to my library?"
    ### Why can't I add volumes to my library?

    The two most common causes for this are:

    - Not having a valid [ComicVine API key](../settings/general.md#comic-vine-api-key) to be able to match or look up volumes.
    - Not having a [root folder](../settings/mediamanagement.md#root-folders) defined.

## Matching

A lot of the problems with matching are caused by [the Special Version of the volume](../general_info/how_to_use.md#special-version) not being determined correctly. This is the first thing that should be checked, in case of problems with matching.

??? question "Why don't my files match to the volume?"
    ### Why don't my files match to the volume?

    There are multiple possible causes to this:

    1. The files are not in the volume folder.

    2. The files aren't for the volume:

        2.1. **Kapowarr is right**  
        If the volume in your library is for a TPB, and the files are for individual issues, then Kapowarr is correct in not matching the files. This often happens in the scenario where a TPB file is (incorrectly) named as "Issue 1". The same goes for deluxe editions: if the file is for a deluxe edition and the volume is for a standard version, then Kapowarr is correct in not matching the file. Almost always, the correct version of the volume can be added to your library, fixing the problem. With the example of the deluxe edition, you can fix it by adding the deluxe edition of the volume to your library instead.

        2.2. **Kapowarr is wrong**  
        Kapowarr tries to automatically determine the [Special Version](../general_info/how_to_use.md#special-version) of a volume, but it isn't always right. Read the linked section for more information on the Special Version of a volume. Editing the volume and overriding the Special Version often resolves problems. Please make an issue on GitHub if the Special Version of a volume was wrongly determined and you think Kapowarr could've done it correctly.

    3. The filename does not follow the [matching criteria](../general_info/matching.md#files-to-issues). The filename does not have to be perfect, but it does have to give the correct information. For example, it often happens that TPB files have "Issue 1" in their filename, which does not meet [rule 2 of the matching criteria for TPB's](../general_info/matching.md#tpb-volume).

    4. The filename is simply not handled properly by Kapowarr. The chance of this happening is slim, but if you think this is the case, please make an issue on GitHub.

??? question "Why do files pop up in Library Import, even though I just imported them?"
    ### Why do files pop up in Library Import, even though I just imported them?

    When you import a file, the matched volume is added to your library (if not already) and the file is matched to one or more issues of the volume. However, the file failed to match to the volume. The file is not matched to anything, so it pops up in Library Import again.
    
    That means it's basically a matter of files not matching to their volume, for which there is a FAQ topic: ["Why don't my files match to the volume?"](#why-dont-my-files-match-to-the-volume)

??? question "Why does Kapowarr not grab the links from a GetComics page even though they work fine?"
    ### Why does Kapowarr not grab the links from a GetComics page even though they work fine?

    GetComics pages often contain downloads for more than what is needed, so Kapowarr filters the links based on what it needs and what it doesn't. If Kapowarr did not download anything from a GetComics page, then it thought the links weren't for any content of interest [that pass the criteria](../general_info/matching.md#getcomics-groups).

    There are multiple possible causes to this:

    1. The links didn't pass the criteria because the [Special Version](../general_info/how_to_use.md#special-version) of the volume is wrong.

    2. Kapowarr correctly thinks that the links do not lead to files that are of interest. For example, Kapowarr will not download a TPB if the volume that is being searched for is a normal, non-TPB, volume. In this case Kapowarr is correct, and if the TPB is desired, that version of the volume should instead be added to your library.

    3. The only working link(s) might be of a service of which the rate limit has already been reached. Then the links work fine, but Kapowarr can't use them at that point in time.

    3. The matching fails because of slightly different namings of the same thing. For example, it might think 'Tom: His Perspective' and 'The Perspective of Tom' do not refer to the same volume, and thus reject it. Another example is 'The Teenage Ninja Turtles' and 'TTNT'.

    4. The only working links are from a service that Kapowarr doesn't support. For example, Kapowarr doesn't support downloading from Google Drive.

    If you still want to download the media, even though Kapowarr thinks it doesn't match to the volume, then you can click the 'Force Download' button in the Manual Search results to force Kapowarr to download all content from the page without any filtering. Kapowarr only renames files that match to issues, so if you forcibly downloaded something and the resulting files aren't renamed, then that's because they didn't match to any issue.