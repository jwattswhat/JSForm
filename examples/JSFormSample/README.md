# JSForm School Bus Sample

Current sample version: `0.1.0-dev` (maintained independently from the JSForm
framework version).

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

To reset only the sample account password without changing any sample data:

```powershell
..\ChurchManager\.runtime-venv\Scripts\python.exe examples\JSFormSample\setup_sample.py --password-only
```

## Run

```powershell
..\ChurchManager\.runtime-venv\Scripts\python.exe examples\JSFormSample\app.py
```

By default, the application prompts for its database password. The password-only
recovery command may explicitly store the restricted sample login in Windows
Credential Manager so a desktop shortcut can start without a console password.

The **Routes** screen demonstrates JSForm's responsive master-detail layout:
ordered stops appear at left and route details at right. Resize the window
narrower than the configured breakpoint to see the panes stack automatically.
