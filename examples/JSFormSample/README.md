# JSForm School Bus Sample

A deliberately small demonstration application for JSForm. It uses fictional
Pine Valley School District data and sample tables prefixed `sb_` in the local
`JSFormTest` database.

## Setup

From the JSForm repository directory, using the ChurchManager runtime Python if
needed:

```powershell
..\ChurchManager\.runtime-venv\Scripts\python.exe examples\JSFormSample\setup_sample.py
```

Enter the local MariaDB username and password when prompted. The reset deletes
and recreates only the sample's `sb_` tables.

## Run

```powershell
..\ChurchManager\.runtime-venv\Scripts\python.exe examples\JSFormSample\app.py
```

No credentials are stored by the sample application.
