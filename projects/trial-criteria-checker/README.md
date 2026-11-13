# trial-criteria-checker

This folder is an older copy of my clinical trial criteria checker, from when I moved it into this repo on November 6, 2026. I work on it in its own repository again now:

https://github.com/jackaI1/trial-criteria-checker

The newer version reads patients from FHIR records, finds studies that are recruiting in one city, uses the registry's structured age and sex fields, and has a score on studies it was never tuned on. The code in this folder still runs (`python3 -m unittest discover -s tests` from this folder), but it won't get those changes.
