# JSForm automated tests

This suite tests JSForm framework modules and assets independently of
ChurchManager. It does not launch the GUI, send email, run reports, modify data,
or exercise ChurchManager modules.

Run the default safe checks from the JSForm folder:

```powershell
python run_jsform_tests.py
```

The optional database checks are read-only. They refuse the live `JSForm`
database and require a database name containing `test`.

```powershell
$env:JSFORM_RUN_DB_TESTS = "1"
$env:JSFORM_TEST_DB_HOST = "192.168.3.200"
$env:JSFORM_TEST_DB_PORT = "3306"
$env:JSFORM_TEST_DB_NAME = "JSFormTest"
python run_jsform_tests.py
```

The runner retrieves the username and password from the `ChurchManager/Test`
entry in Windows Credential Manager. Do not place the password in an environment
variable or command line. A missing credential or mismatched username stops the
test before connecting.
