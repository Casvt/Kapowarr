On this page, you can find instructions on how to manually install Kapowarr (directly on the host) and on how to update your manual installation.

## Installation

!!! warning
	These instructions are still under construction.

=== "Windows"
    On Windows, there are a couple of extra steps involved.  

    1. [Download and install Python](https://www.python.org/downloads/). This is the framework Kapowarr runs on top of.  
       _Make sure you select to add Python to PATH when prompted. This will make installing requirements much easier._
    2. Download (or clone) the [latest Kapowarr release](https://github.com/Casvt/Kapowarr/releases/latest).  
    3. Extract the zip file to a folder on your machine.  
       We suggest something straightforward - `C:\services\Kapowarr` is what we'll use as an example.
    4. Install the required python modules (found in `requirements.txt`).
       This can be achieved from a command prompt, by changing to the folder you've extracted Kapowarr to and running a python command.
       ```powershell
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

## Updating install

Coming Soon.
