# JSForm School Bus Sample

A deliberately small demonstration application for JSForm. It uses fictional
Pine Valley School District data in its own local `JSFormSample` database.

## Setup

From the JSForm repository directory, using the ChurchManager runtime Python if
needed:

```powershell
..\ChurchManager\.runtime-venv\Scripts\python.exe examples\JSFormSample\setup_sample.py
```

Enter an administrative MariaDB password, then choose a password for the new
restricted `jsform_sample` account. The installer creates the isolated database,
minimal framework configuration, and fictional data. Later runs reset only the
sample's `sb_` domain tables.

## Run

```powershell
..\ChurchManager\.runtime-venv\Scripts\python.exe examples\JSFormSample\app.py
```

No credentials are stored by the sample application.
