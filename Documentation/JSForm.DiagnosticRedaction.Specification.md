# JSForm final diagnostic redaction specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 29, 2026 — 433 JSForm tests passed (2 skipped) and 1,063
ChurchManager tests passed (25 skipped).

Date: August 29, 2026

Framework owner: JSForm

Application owner: optional application-specific redactors and the decision to
create or share a support package

## 1. Purpose

JSForm shall prevent common credential and secret representations from reaching
diagnostic logs, error dialogs, or support-package files. Redaction shall remain
an internal framework behavior and shall not require applications to change
their existing error-reporting calls or parameters.

This specification addresses item 7 in the JSForm Codex Security remediation
queue: **Strengthen final diagnostic redaction.**

## 2. Current condition

`error_redaction.redact_text()` currently covers credentials embedded in URI
authority sections, `Authorization:` header lines, password command-line
arguments, and application-supplied redactors. Mapping keys are checked when
values are supplied as mappings.

The text redactor does not consistently cover credentials rendered inside
plain key-value text, JSON or Python-style mappings, query strings, cookie and
authentication headers embedded within connector messages, or several common
connector exception formats. In addition, application-provided user messages
can currently reach the error dialog without a final framework redaction pass.

## 3. Security invariants

1. A value associated with a recognized sensitive name shall be replaced with
   `[REDACTED]` in supported textual representations.
2. Redaction shall occur before diagnostic text is persisted and again at each
   final disclosure boundary: error display and support-package construction.
3. Support-package contents shall be redacted from the bytes actually selected
   for the archive, even if an older log or a custom diagnostics provider
   supplied insufficiently redacted text.
4. A redactor failure shall fail safely: it shall not restore a secret, expose
   the redactor exception, or prevent other framework redactors from running.
5. Redaction shall be deterministic, bounded against pathological input, and
   shall not parse or execute diagnostic content.
6. The framework shall not log the original secret as part of a redaction error.

## 4. Sensitive names

The existing case-insensitive sensitive-name policy remains the canonical
source. It includes password/passwd/pwd, secret, token, API key, authorization,
cookie, credential, connection string, hash, salt, SMTP password, and database
password forms.

Name matching shall tolerate common separators and casing, including hyphens,
underscores, spaces, and compact spellings. It shall avoid treating ordinary
unrelated words as sensitive merely because they contain a short fragment such
as `pwd` inside a longer word.

## 5. Text representations to cover

The framework redactor shall recognize and preserve the non-secret structure of
these bounded forms while replacing only the associated value:

- `name=value`, `name: value`, and similar comma/semicolon-delimited pairs;
- quoted JSON and Python-style mapping pairs such as
  `{"token": "value"}` and `{'password': 'value'}`;
- URL query and form-style pairs such as `?api_key=value&mode=test`;
- URI authority credentials such as `scheme://user:password@host`;
- command-line secret arguments using `--name value` or `--name=value`;
- authorization, proxy-authorization, cookie, and set-cookie header values;
- common connector messages that render configuration or keyword arguments,
  including database, mail, HTTP, cloud, and operating-system credential-store
  exceptions.

Matching shall cover quoted and unquoted scalar values, stop at the appropriate
delimiter, preserve surrounding punctuation when practical, and remain
idempotent when applied more than once. It is not required to infer an unlabeled
secret from arbitrary prose.

## 6. Structured diagnostics

`safe_context()` and `safe_diagnostics()` shall recursively normalize only the
currently supported bounded scalar/list/mapping structures. Sensitive mapping
keys shall redact their entire values. Non-sensitive strings shall pass through
the strengthened text redactor. Unsupported objects shall continue to be
represented by a type placeholder and shall never be stringified for export.

Depth, collection count, key length, and text length shall be bounded. Cyclic
or excessively nested input shall produce a safe placeholder rather than an
exception or unbounded traversal.

## 7. Error-display boundary

Immediately before calling the dialog implementation, JSForm shall redact the
final user-visible application name and optional user message using the same
framework and application redactors. The error ID and fixed framework guidance
shall retain their existing presentation.

Application-provided messages remain supported, but a message containing a
recognized secret representation shall display `[REDACTED]`. Redaction shall
also occur within `error_dialog.show_error_dialog()` so direct callers receive
the same final protection.

## 8. Support-package boundary

Immediately before archive creation, JSForm shall re-redact every approved text
payload selected for the package, including JSONL log records, the manifest's
textual metadata, and application diagnostics. Binary or unapproved files shall
remain excluded.

Redaction shall operate on parsed JSON values where valid and use bounded text
redaction as a safe fallback for malformed historical lines. The package shall
be built only from the redacted bytes. Existing atomic creation, no-overwrite,
allowlist, hash-manifest, and archive-readback verification behavior shall be
preserved.

## 9. Compatibility

The following public behavior shall remain compatible:

- `redact_text`, `safe_context`, and `safe_diagnostics` retain their public
  names and existing parameters;
- error-reporting configuration and application-supplied redactors remain
  supported;
- `report_exception`, `error_boundary`, and `create_support_package` retain
  their calls and return values;
- support-package filenames, manifest verification, error IDs, log rotation,
  and retention remain unchanged.

The intentional behavior change is that recognized secret-shaped values may no
longer appear verbatim in logs, dialogs, or support packages. Applications must
not depend on secret text surviving diagnostic processing.

## 10. Documentation

Implementation shall update the framework reference, public API documentation,
support guidance, relevant docstrings, and the JSForm roadmap. Examples shall
use fictional values only.

## 11. Verification

Automated tests shall prove at minimum:

1. each representation in section 5 is redacted without exposing its value;
2. mixed casing, separators, quoting, punctuation, multiline connector errors,
   and repeated application are handled safely;
3. benign neighboring fields and useful non-secret error detail are preserved;
4. framework and failing application redactors fail safely;
5. nested, cyclic, oversized, and unsupported structured diagnostics are
   bounded and safe;
6. an application user message is redacted at the final dialog boundary;
7. a deliberately insufficiently redacted historical log is re-redacted in
   the support package;
8. malformed historical JSONL cannot bypass fallback redaction;
9. archive contents and manifest hashes verify against the final redacted bytes;
10. existing JSForm and ChurchManager test suites remain compatible.

No test shall use a real credential, transmit a support package, or contact an
external connector.

## 12. Completion criteria

This item is complete when the implementation, documentation, and regression
tests satisfy this specification; the focused tests and full JSForm and
ChurchManager suites pass; and the roadmap records the verified result. GUI
visual verification is not required because this change preserves the existing
dialog layout and changes only message normalization.
