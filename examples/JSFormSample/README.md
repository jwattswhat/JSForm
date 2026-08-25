# JSForm School Bus Sample

Current sample version: `0.1.0-dev` (maintained independently from the JSForm
framework version).

A deliberately small demonstration application for JSForm. It uses fictional
Pine Valley School District data in its own local `JSFormSample` database.
The launchers import the installed `jsform-desktop` distribution; they do not
add a source checkout to Python's import path.

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

The main window's File, Records, Reports, Tools, and Help menus are defined in
`Menus/main.menu.json`. Python registers the command handlers; the JSON contains
only presentation and stable command names. The visible navigation and tool
buttons dispatch through the same command registry as the menu items, showing how
one command can be shared safely by multiple interface surfaces.

The launcher configures `assets/school-bus-routes.ico` before creating its
forms, demonstrating how an application overrides JSForm's bundled framework
icon without changing framework code.

**Tools > Designers** provides all three JSForm visual design tools:

- **Screen Designer** customizes the sample's form layouts.
- **Report Designer** customizes the route-manifest report.
- **Menu Designer** customizes the application menu and uses the sample's
  approved command catalog.

Each designer stores editable files under the current user's local
`JSFormSample` application-data folder. The Forms, Reports, and Menus folders
shipped with the sample remain protected starters. Saved screen and report
customizations are used by the sample immediately when those definitions are
next opened; a saved menu customization is loaded on the next application
launch.
