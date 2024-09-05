# Reporting

This page covers how to get in contact, which platform to use and how to properly share information like logs and errors.

## Choosing a Platform

If you have a question, first check the [FAQ](./faq.md) and otherwise visit the [Discord server](https://discord.gg/nMNdgG7vsE).  
If you experience behaviour that you are unsure of if it's correct, check the ['General Information' page](../general_info/workings.md).  
If you are sure that something is going wrong (bug) or is missing (feature), create a [GitHub issue](https://github.com/Casvt/Kapowarr/issues).

## Reporting a Bug

If you experience behaviour that is not correct, you should make a 'bug report':

1. Enable [debug logging](../settings/general.md#log-level) in the settings.
2. Reproduce the error (this way it will occur with debug logs enabled).
3. Collect all the relevant logs. Preferably starting from when you started reproducing, but _AT LEAST_ the complete error (a.k.a. traceback).
4. Collect the information found at System -> Status -> About.
5. On the [GitHub issues page](https://github.com/Casvt/Kapowarr/issues), make a new issue and choose the 'Bug report' template. Fill in each field in the template with the information from your system.
6. Make sure to properly format code and errors! Otherwise it's not readable. See the tip below.

### Formatting code and errors

!!! tip "Formatting code and errors in GitHub"
    If you want to share logs, type the following when making a GitHub issue:

    &#96;&#96;&#96;  
    [2024-01-20 11:20:29][MainThread][INFO] Starting up Kapowarr  
    [2024-01-20 11:20:29][MainThread][INFO] Kapowarr running on http://0.0.0.0:5656/  
    [2024-01-20 11:20:29][Thread-1][INFO] Added task: Update All (1)  
    [2024-01-20 11:20:30][Task Handler][INFO] Finished task Update All  
    &#96;&#96;&#96;

    It will look like this:

    ```
    [2024-01-20 11:20:29][MainThread][INFO] Starting up Kapowarr
    [2024-01-20 11:20:29][MainThread][INFO] Kapowarr running on http://0.0.0.0:5656/
    [2024-01-20 11:20:29][Thread-1][INFO] Added task: Update All (1)
    [2024-01-20 11:20:30][Task Handler][INFO] Finished task Update All
    ```

    If you want to share code or errors, type the following when making a Github issue:
    
    &#96;&#96;&#96;python  
    Traceback (most recent call last):  
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 1455, in wsgi_app  
        &emsp;response = self.full_dispatch_request()  
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 869, in full_dispatch_request  
        &emsp;rv = self.handle_user_exception(e)  
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 867, in full_dispatch_request  
        &emsp;rv = self.dispatch_request()  
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 852, in dispatch_request  
        &emsp;return self.ensure_sync(self.view_functions[rule.endpoint])(\*\*view_args)  
    File "/usr/serverApps/Kapowarr/frontend/api.py", line 64, in wrapper  
        &emsp;return method(*args, \*\*kwargs)  
    File "/usr/serverApps/Kapowarr/frontend/api.py", line 207, in wrapper  
        &emsp;result = method(*args, \*\*kwargs)  
    File "/usr/serverApps/Kapowarr/frontend/api.py", line 398, in api_library_import  
        &emsp;result = propose_library_import(limit, only_english)  
    File "/usr/serverApps/Kapowarr/backend/library_import.py", line 174, in propose_library_import  
        &emsp;search_results = run(__search_matches(  
    File "/usr/lib/python3.8/asyncio/runners.py", line 44, in run  
        &emsp;return loop.run_until_complete(main)  
    File "/usr/lib/python3.8/asyncio/base_events.py", line 616, in run_until_complete  
        &emsp;return future.result()  
    File "/usr/serverApps/Kapowarr/backend/library_import.py", line 37, in __search_matches  
        &emsp;responses = await gather(*tasks)  
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 597, in search_volumes_async  
        &emsp;return self.__process_search_results(query, results)  
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 483, in __process_search_results  
        &emsp;results = [self.__format_volume_output&#40;r) for r in results]  
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 483, in  
        &emsp;results = [self.__format_volume_output&#40;r) for r in results]  
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 303, in __format_volume_output  
        &emsp;result['volume_number'] = int(volume_result.group(1))  
    ValueError: invalid literal for int() with base 10: 'i'  
    &#96;&#96;&#96;
    
    It will look like this:
    
    ```python
    Traceback (most recent call last):
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 1455, in wsgi_app
        response = self.full_dispatch_request()
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 869, in full_dispatch_request
        rv = self.handle_user_exception(e)
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 867, in full_dispatch_request
        rv = self.dispatch_request()
    File "/home/nogardvfx/.local/lib/python3.8/site-packages/flask/app.py", line 852, in dispatch_request
        return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)
    File "/usr/serverApps/Kapowarr/frontend/api.py", line 64, in wrapper
        return method(*args, **kwargs)
    File "/usr/serverApps/Kapowarr/frontend/api.py", line 207, in wrapper
        result = method(*args, **kwargs)
    File "/usr/serverApps/Kapowarr/frontend/api.py", line 398, in api_library_import
        result = propose_library_import(limit, only_english)
    File "/usr/serverApps/Kapowarr/backend/library_import.py", line 174, in propose_library_import
        search_results = run(__search_matches(
    File "/usr/lib/python3.8/asyncio/runners.py", line 44, in run
        return loop.run_until_complete(main)
    File "/usr/lib/python3.8/asyncio/base_events.py", line 616, in run_until_complete
        return future.result()
    File "/usr/serverApps/Kapowarr/backend/library_import.py", line 37, in __search_matches
        responses = await gather(*tasks)
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 597, in search_volumes_async
        return self.__process_search_results(query, results)
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 483, in __process_search_results
        results = [self.__format_volume_output(r) for r in results]
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 483, in
        results = [self.__format_volume_output(r) for r in results]
    File "/usr/serverApps/Kapowarr/backend/comicvine.py", line 303, in __format_volume_output
        result['volume_number'] = int(volume_result.group(1))
    ValueError: invalid literal for int() with base 10: 'i'
    ```
    
    See the difference? That's why it's important to properly format logs and code when sharing them.
