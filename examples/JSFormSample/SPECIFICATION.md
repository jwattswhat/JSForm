# JSForm School Bus Sample specification

**Status:** Complete and visually approved

**Date:** August 14, 2026

## Purpose

Provide a small, fictional, runnable application that demonstrates JSForm as a
framework without importing or depending on ChurchManager.

## Boundaries

- The sample uses its own local `JSFormSample` MariaDB database and restricted
  `jsform_sample` account.
- Every domain table begins with `sb_`; the database also contains the minimal
  JSForm-owned `jsConfig` and `jsOptions` framework tables.
- Reset operations may drop and recreate only `sb_` tables.
- The sample has no login, users, roles, or visible security administration.
- Runtime authorization uses JSForm's allow-all policy.
- No real email is sent.
- All people, schools, addresses, telephone numbers, and routes are fictional.

## Small domain model

- School
- Driver
- Bus
- Route
- Ordered Route Stop
- Student assigned to a Route Stop

## Demonstrated JSForm behavior

- JSON-defined screens and responsive layout;
- navigation, create, update, and delete;
- required and optional fields;
- text, number, checkbox, date, time, phone, email, and multiline controls;
- lookup controls and parent-child forms;
- ordered child records;
- database constraints and friendly failures;
- a visual route-manifest report;
- screen/report designer compatibility;
- centralized diagnostics;
- fake mail preview only.

## Acceptance

The sample is successful when a developer can reset its fictional data, launch
the application, maintain each entity, open a route's ordered stops, assign a
student to a stop, and generate a route manifest without any ChurchManager code
or data.
