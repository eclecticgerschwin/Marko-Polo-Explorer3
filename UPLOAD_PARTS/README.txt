HOW TO UPLOAD (all files in this folder)
=========================================

1. In Coda, upload ALL files from this folder into the markopolo/ folder
   on the server (same place as version.json). Upload them one at a time
   if needed - each part is only ~23 MB.

     MarkoPoloExplorer.exe.part01 / 02 / 03
     MarkoPoloExplorer-Windows.zip.part01 / 02 / 03
     version.json          (overwrites the old one)
     join.php

2. Open this address once in your browser:

     http://marko.com.hr/markopolo/join.php

   You should see:
     OK: built MarkoPoloExplorer.exe (64.2 MB) from 3 parts
     OK: built MarkoPoloExplorer-Windows.zip (63.8 MB) from 3 parts

   The parts are deleted automatically after joining.

3. Also upload the updated  www/index.html  to the markopolo/ folder.

4. Test: http://marko.com.hr/markopolo/MarkoPoloExplorer.exe should
   download the 64 MB exe. Then delete join.php from the server (optional).

NOTE: this build is version 08082613. The old C-version app on your
Windows test machine thinks it is 08082615, so its Update button will say
"latest version" - just download the new exe from the website once on that
machine. All future builds will update normally.
