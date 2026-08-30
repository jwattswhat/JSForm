# JSForm protected SMTP transport specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 29, 2026 — 427 JSForm tests passed (2 skipped) and 1,063
ChurchManager tests passed (25 skipped).

Date: August 29, 2026

Framework owner: JSForm

Application owner: SMTP server selection, environment classification, sender
identity, credential targets, and whether unauthenticated loopback relay is
enabled

## 1. Purpose

JSForm shall prevent authentication credentials from being transmitted through
an SMTP connection that has not established authenticated TLS. Ordinary remote
delivery shall require either implicit TLS or successful STARTTLS before login
or message transmission.

This specification addresses item 6 in the JSForm Codex Security remediation
queue: **Require protected SMTP transport.**

## 2. Current condition

`MailSettings.security` currently accepts `ssl`, `starttls`, and `plain`.
`SMTPTransport.deliver()` uses implicit TLS for `ssl`, upgrades with STARTTLS for
`starttls`, and otherwise uses a plaintext SMTP connection. The transport then
resolves target credentials and calls `login()` whenever authentication is
configured.

Consequently, `security="plain"` with a username and password or protected
credential target can transmit credentials without encryption. Plain mode can
also send message content to any configured remote host.

Roadmap item 5 already moved database-backed SMTP secrets to protected
credential targets. This item secures the network boundary at which those
credentials and messages are used.

## 3. Security invariants

1. SMTP authentication shall occur only through implicit TLS or after STARTTLS
   completes successfully.
2. Credential lookup shall not occur until the selected protected connection is
   established and immediately before authentication.
3. A failed or unavailable STARTTLS upgrade shall prevent credential lookup,
   login, and message transmission.
4. Plain SMTP shall never use a username, password, credential target, token, or
   other authentication material.
5. Plain SMTP shall never connect to a remote, wildcard, unspecified, multicast,
   broadcast, link-local, or non-loopback destination.
6. An optional plain relay exception shall be limited to an explicit
   application choice, an unauthenticated loopback host, and message delivery
   from the same computer.
7. TLS certificate and hostname verification shall remain enabled and shall not
   be bypassable through settings.
8. Validation failures shall occur before network access whenever the unsafe
   state is knowable from configuration.
9. Errors shall not disclose credentials, credential targets, message bodies,
   recipient lists, or raw provider details.

## 4. Ownership boundary

JSForm owns:

- validation of protected SMTP modes;
- strict loopback classification for any plain relay exception;
- connection ordering, STARTTLS enforcement, and final authentication checks;
- safe transport errors;
- injectable SMTP/TLS seams for testing; and
- reusable documentation and tests.

Applications own:

- the configured server, port, sender, and credential target;
- authorization to edit or test settings;
- whether an unauthenticated loopback relay is permitted at all;
- environment-specific settings and user-facing confirmation;
- provider guidance and credential provisioning; and
- audit and delivery policy.

JSForm shall not encode ChurchManager names, permission identifiers, provider
accounts, database tables, or congregation policy.

## 5. Included scope

Implementation shall update:

- `MailSettings` validation and its documented contract;
- `SMTPTransport` connection and authentication boundaries;
- safe error normalization for TLS negotiation and configuration failures;
- public docstrings and framework documentation;
- focused tests using fake SMTP connections and credential providers; and
- roadmap item 6 after verification.

No JSON Schema change is required.

## 6. Excluded scope

This item shall not:

- change ChurchManager source, settings screens, permissions, or database
  schema;
- connect to a real SMTP server or send a real message during tests;
- access real credentials or production data;
- implement OAuth or provider-specific authentication;
- add custom certificate authorities or certificate-pinning settings;
- permit certificate-verification disablement;
- strengthen diagnostic redaction beyond the transport errors included here,
  because that remains roadmap item 7; or
- change database-password handling, which remains roadmap item 8.

## 7. MailSettings contract

The existing positional field order and meanings shall remain compatible.
`security` shall continue to accept the canonical values `ssl`, `starttls`, and
`plain`, case-insensitively.

An optional Boolean field named `allow_plain_loopback` shall be appended to
`MailSettings` with a default of `False`. Appending preserves existing
positional callers.

Validation rules shall be:

| Security | Authentication | Host | Result |
| --- | --- | --- | --- |
| `ssl` | Optional | Any valid application host | Allowed |
| `starttls` | Optional | Any valid application host | Allowed |
| `plain` | Any authentication configured | Any | Rejected |
| `plain` | None | Non-loopback | Rejected |
| `plain` | None | Loopback, exception false | Rejected |
| `plain` | None | Loopback, exception true | Allowed |

The loopback exception must be explicit. Merely choosing `plain`, using a common
development port, setting test mode elsewhere, or naming a host `local` shall
not enable it.

## 8. Loopback classification

Only these destinations qualify:

- the exact hostname `localhost`, after trimming and case folding;
- an IPv4 address within `127.0.0.0/8`; or
- the IPv6 loopback address `::1`, including its bracketed host form `[::1]`.

The following do not qualify:

- `0.0.0.0`, `::`, wildcard or unspecified addresses;
- private-network addresses such as `10.0.0.0/8`, `172.16.0.0/12`, and
  `192.168.0.0/16`;
- link-local, multicast, or broadcast addresses;
- hostnames such as `mail.local`, `localhost.example.org`, or trailing-dot
  variants;
- decimal, hexadecimal, octal, shortened, integer, mapped, zone-indexed, or
  other alternative IP representations not accepted by the strict parser; and
- a remote hostname that DNS happens to resolve to loopback.

JSForm shall classify the supplied host text without DNS resolution. This avoids
network access during validation and prevents DNS rebinding from creating a
plain-relay exception.

## 9. Connection behavior

### 9.1 Implicit TLS

For `ssl`, JSForm shall create `smtplib.SMTP_SSL` with a default verified
`ssl.SSLContext`. Credential resolution, login, and message transmission occur
only after construction returns successfully.

### 9.2 STARTTLS

For `starttls`, JSForm shall:

1. create an ordinary SMTP connection with the configured timeout;
2. issue `EHLO` when required by the library contract;
3. require the server to advertise STARTTLS before attempting upgrade;
4. call `starttls()` with a default verified context;
5. issue a fresh `EHLO` after successful upgrade;
6. resolve credentials only after the upgrade;
7. authenticate when configured; and
8. send the message.

If STARTTLS is not advertised, negotiation fails, or the connection drops,
JSForm shall not resolve credentials, call login, or send the message.

### 9.3 Explicit loopback relay

For allowed `plain` loopback delivery, JSForm shall:

- use ordinary `smtplib.SMTP`;
- perform no credential-store lookup;
- never call `login()`;
- send only after validation has confirmed the strict loopback exception; and
- retain the same bounded timeout.

## 10. Final authentication boundary

Configuration validation is not sufficient by itself. Immediately before
`login()`, `SMTPTransport` shall assert that the active mode is `ssl` or that
STARTTLS completed successfully. This final boundary protects against future
caller or control-flow changes that bypass initial validation.

The transport shall not represent TLS state solely by trusting the original
settings string. It shall set an internal local delivery-state value only after
the relevant secure connection or upgrade succeeds. This value shall not be a
public application-controlled option.

## 11. TLS context and certificate validation

JSForm shall continue to use `ssl.create_default_context()` without disabling
hostname checks or certificate verification. No `verify=False`, unverified
context, empty trust store, custom hostname override, or exception-driven
plaintext fallback is permitted.

An invalid, expired, mismatched, untrusted, or otherwise rejected certificate
shall fail delivery. The transport shall never retry the same destination using
plain SMTP.

## 12. Error handling

Unsafe configuration shall raise `MailConfigurationError` before opening a
socket. TLS, certificate, network, authentication, and provider failures shall
surface as the existing safe `MailDeliveryError` category.

User-facing text and `DeliveryResult.message` shall use fixed safe descriptions.
They shall not contain:

- the credential or target;
- the raw SMTP response;
- certificate subject details;
- server-provided diagnostic text;
- sender, recipient, subject, or body content; or
- a full remote hostname when unnecessary.

Exception chaining may preserve a technical cause only when the cause cannot
contain credentials or private message content. Otherwise it shall be
suppressed or replaced with a safe cause.

## 13. Compatibility requirements

The following shall remain intact:

- current `MailSettings` positional construction;
- `MailService`, `SMTPTransport`, `MailMessage`, and `DeliveryResult` public
  names;
- direct in-memory username/password compatibility over protected modes;
- target-backed credential rotation on each delivery;
- implicit TLS and STARTTLS providers;
- unauthenticated protected SMTP;
- fresh per-recipient RFC messages and attachments; and
- the historical `clsSMTP.sendeMail(...)` facade through protected settings.

Previously accepted authenticated plaintext SMTP is intentionally rejected.
Previously accepted remote unauthenticated plaintext SMTP is also rejected.
These are security enforcement changes, not compatibility regressions.

## 14. Documentation changes

Implementation shall update:

- `Documentation/JSForm_Framework.md` with the transport matrix and loopback
  rule;
- public contract documentation and docstrings;
- examples that imply remote or authenticated plain SMTP;
- the approved specification status; and
- the JSForm roadmap after verification.

Documentation shall keep roadmap item 5 credential storage distinct from item
6 transport encryption.

## 15. Testing requirements

Focused tests shall prove:

1. SSL permits authenticated target and in-memory credential delivery;
2. STARTTLS permits authentication only after successful upgrade;
3. credential lookup occurs after STARTTLS and immediately before login;
4. missing STARTTLS capability prevents lookup, login, and send;
5. STARTTLS failure prevents lookup, login, and send;
6. certificate or SSL construction failure never falls back to plain;
7. authenticated plain settings fail validation before network access;
8. target-backed plain settings fail before credential lookup or network access;
9. unauthenticated remote plain settings fail before network access;
10. plain loopback fails unless the exception is explicitly enabled;
11. explicitly allowed unauthenticated `localhost`, `127.0.0.1`, another
    `127/8` address, `::1`, and `[::1]` can send without login;
12. whitespace and case normalization work only for the exact `localhost` name;
13. wildcard, unspecified, private, link-local, multicast, mapped, encoded,
    shortened, trailing-dot, suffix, and DNS hostname variants are rejected;
14. loopback validation performs no DNS lookup;
15. final authentication enforcement rejects an artificially inconsistent
    delivery state;
16. TLS uses the default verified context and no verification-disable path;
17. safe errors and results contain no credential, target, raw response,
    recipient, subject, or body;
18. credentials rotate between protected deliveries;
19. unauthenticated SSL and STARTTLS delivery remain supported;
20. attachments and separate-recipient behavior remain unchanged;
21. historical facade tests use only protected settings;
22. no test accesses a real credential vault, SMTP provider, DNS, or network;
23. the complete JSForm suite passes; and
24. ChurchManager's suite passes against the updated framework without a
    ChurchManager source change required by this item.

## 16. Acceptance criteria

The item is complete when:

1. no authenticated plaintext configuration can open a connection or resolve a
   credential;
2. remote plaintext delivery is rejected;
3. the sole plaintext exception is explicit, unauthenticated, and strictly
   loopback;
4. STARTTLS failure cannot reach credential lookup, login, or send;
5. the final authentication boundary independently enforces protected state;
6. certificate verification remains mandatory;
7. ordinary SSL and STARTTLS delivery remains compatible;
8. an independent read-only security and compatibility review finds no
   surviving included downgrade or plaintext path;
9. focused tests, the full JSForm suite, and ChurchManager's suite pass;
10. documentation matches the implemented behavior; and
11. roadmap item 6 is marked implemented only after verification.

## 17. Implementation sequence after approval

1. Add characterization tests for SSL, STARTTLS, plain mode, credential timing,
   and current public signatures.
2. Add strict loopback classification and settings validation tests.
3. Implement explicit plain-loopback opt-in and reject every other plain mode.
4. Require advertised and successful STARTTLS before protected delivery.
5. Add the final local TLS-state authentication check.
6. Normalize included errors without exposing sensitive provider data.
7. Challenge alternative host representations, downgrade paths, direct
   callers, and legitimate protected providers.
8. Update docstrings and framework documentation.
9. Run focused tests.
10. Perform one independent read-only bypass and compatibility review.
11. Correct confirmed in-scope findings and rerun focused tests.
12. Run the complete JSForm and ChurchManager suites.
13. Mark the specification and roadmap implemented only after all acceptance
    criteria pass.

## 18. Approval

Approval authorizes implementation of this specification within JSForm only.
It does not authorize ChurchManager source changes, real credential access,
production database access, DNS or network activity, sending email, deployment,
OAuth work, custom trust-store changes, or later roadmap items.
