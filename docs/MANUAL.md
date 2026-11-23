# Beginner manual

This guide takes you from an offline example to a manually approved run against **your own** Gmail account. No account, OAuth consent, mailbox or website setting was accessed during preparation. Official instructions were reviewed on **2026-11-23**; [the source/status table](SETUP_SOURCES.md) separates that review from live checks still pending.

## 1. Understand the workflow

The tool reads project-alert emails, extracts opportunities, applies your TXT preferences and writes a local `.xlsx` file. It supports the source application's two formats: 99Freelas HTML containing a project anchor and paragraph metadata, and Freelancer.com text digests with title/`Budget:`/`Skills:`/`Description:` blocks and project links. MIME alternatives/nested parts are handled; HTML-only Freelancer digests are converted to text before the same block parser.

**Upwork and Fiverr are potential future integrations, not supported platforms.**

This is not a website scraper or job-application bot. Platform accounts and alert delivery are set up manually by you. Other notification types and changed templates can be unsupported. The program does not fetch project pages, resolve redirect/tracking wrappers, translate text, verify employers, submit bids or send messages. Sender-domain checks reject obvious lookalike domains but are not cryptographic authentication.

The **Budget (as emailed)** column retains the supplied budget text, including any currency label. No USD conversion, exchange-rate calculation or financial interpretation is performed. The fictional fixtures explicitly identify BRL/USD. If an email omits its currency or uses an ambiguous `$`, the tool leaves that ambiguity intact; it never infers USD or BRL from the platform. Do not compare mixed-currency amounts as a common-currency total. Budgets do not affect ranking. Scores are preference matches, not probability of success or expected earnings. Collected timestamps use UTC; human application dates use `YYYY-MM-DD`.

## 2. Install Python and run offline first

On Windows, get Python from [the official Windows downloads](https://www.python.org/downloads/windows/). The current [Windows guide](https://docs.python.org/3/using/windows.html) describes Python Install Manager and `py install <version>`. If Python 3.12 is absent, install the manager, reopen PowerShell and run `py install 3.12`. Check `py -3.12 --version`. An older launcher may not implement `py install`; follow the official guide rather than replacing another project's environment. This project was validated with Python 3.12; other versions are not claimed tested.

Open PowerShell in this project's folder (File Explorer's address bar can open PowerShell, or use `Set-Location` with your own folder). Run:

```powershell
py -3.12 -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r requirements.txt -c constraints.txt
.\.venv-win\Scripts\python.exe -m job_monitor demo --preferences preferences.example.txt --output artifacts/demo.xlsx
```

No activation command or PowerShell execution-policy change is required. All commands explicitly use the virtual environment's interpreter. Dependencies must be installed once while online; the subsequent demo is offline. On Linux/macOS use `python3.12 -m venv .venv`, then `.venv/bin/python` for pip/module commands. OS virtual-environment support may need installation if ensurepip is missing. Native Windows/macOS installation remains for your local acceptance.

Open the workbook in Excel or a compatible viewer. Expect three opportunities, two discarded/excluded rows and one duplicate on the first run. Run again: zero new rows and six duplicates. Close Excel before each write. The [included sample](../examples/demo-output.xlsx) contains only invented data; the [table preview](demo-workbook-preview.png) is rendered from it, not a native Excel screenshot.

## 3. Create your preferences safely

In PowerShell, copy only if a personal file is absent:

```powershell
if (Test-Path preferences.txt) {
    Write-Host "Keeping existing preferences.txt."
} else {
    Copy-Item preferences.example.txt preferences.txt
}
notepad preferences.txt
```

Read [the full format and worked examples](PREFERENCES.md). Start with a few terms relevant to incoming job descriptions; terms can be in their original language. The program normalizes case and combining accents, not meaning or language. Negative weights, all-term/paired-group bonuses, conditional caps and explicit exclusions are supported. Comments occupy separate lines. Invalid settings fail with line numbers; configuration is never executed or rewritten.

For example, the invented Python CSV automation alert scores `20 + 10 + 8 + 6 + 15 + 9 = 68`; the spreadsheet-only example is capped at 12; an explicit unpaid-trial exclusion wins over positive matches. Repeated terms count once per rule. Historical rows keep their original score/fingerprint. Use a new **demo** output filename to compare rule versions without losing live notes.

## 4. Create and secure a dedicated Gmail account

Create your own account through [Google's account-creation guide](https://support.google.com/accounts/answer/27441). Select an account with Gmail enabled; choosing an existing non-Gmail address alone does not give this tool a Gmail mailbox. Use the dedicated account for job alerts rather than personal/work correspondence.

Set recovery options and enable [2-Step Verification](https://support.google.com/accounts/answer/185839) in Google Account security settings. Retain recovery codes privately. The application uses OAuth: **never put a Google password, app password, recovery code or browser cookie in its configuration**. If organization policies block authorization, use an account you control or ask your administrator; do not bypass policy. Account creation/security setup are user steps, not executed by this project.

## 5. Configure platform accounts and actual email alerts

Use only accounts you are entitled to operate. Already have a platform account? Configure it instead of creating a duplicate solely for this demonstration. Freelancer's [FAQ](https://www.freelancer.com/faq/view.php) limits members to one account.

### 99Freelas

Follow the official [freelancer registration guide](https://99freelas.zendesk.com/hc/pt-br/articles/360008417953-Criando-uma-conta-de-Freelancer): choose the worker/freelancer signup option, supply your own details and confirm the email. For an existing profile, manage its email/contact settings through the site; no particular current email-change menu is asserted here.

The [profile guide](https://99freelas.zendesk.com/hc/pt-br/articles/360008418293-Preenchendo-o-seu-perfil-Freelancer) distinguishes areas of interest, which drive project notifications, from skills used to describe your work. Set both accurately. The official [notifications guide](https://99freelas.zendesk.com/hc/pt-br/articles/1500007817621-Gerenciando-minhas-notifica%C3%A7%C3%B5es-e-alertas-freelancer) describes a Menu → Account → Notifications and Alerts route and new-project notifications with frequency/time selection. Those are English translations of the Portuguese help labels, not a claim that the live site displays English menus. The article is older; the signed-in UI, delivery timing and current email HTML remain pending your verification. Message/proposal/newsletter alerts are not all project alerts.

### Freelancer.com

Use the official [getting-started guide](https://www.freelancer.com/support/general/how-to-get-started-at-freelancer-com), complete your profile/skills and [verify your email](https://www.freelancer.com/support/profile/verifying-my-email-address). Use your dedicated Gmail address where permitted.

The official [finding-projects guide](https://www.freelancer.com/support/project/how-to-find-projects) says opted-in newsletter emails can notify you about projects matching skills. The FAQ directs users to notification settings; the email-verification guide uses an Email & Notifications label. Review your account's actual email/project/newsletter controls. Exact toggle names are not asserted because the sources differ and no signed-in UI was tested. [Saved-search Receive Alerts](https://www.freelancer.com/support/project/saving-my-project-searches) is documented for Saved Alerts notifications; it is not assumed to deliver the email digest this parser needs.

Wait for a real alert in your own dedicated inbox and verify its format before expecting automatic parsing. Source-format compatibility does not prove every current platform email is supported. Do not buy subscriptions or create accounts just to make the offline demo run.

## 6. Manually create the required Gmail label/filter

This application requires an existing label matching `label` in your live configuration, initially **JobAlerts**. Following Google's [label guide](https://support.google.com/mail/answer/118708), use the create-label control beside Labels and enter that name. You may initially apply it manually to a small number of your own project alerts.

Following Google's [filter guide](https://support.google.com/mail/answer/6579), open search options, build criteria from an actual platform alert's sender/subject, test the search, choose Create filter and select the label action. Choose only the actions you want; marking read, archiving, forwarding or deleting is not required by this app. There are no hardcoded personal sender addresses in this tool: inspect your own authentic alert rather than treating fixture addresses as official senders. Keep unrelated account/payment messages out of the label.

The API combines that label with `query`, initially `newer_than:30d`. It lists matching messages with pagination up to `max_messages` and excludes Spam/Trash. No unread filter is required. If you choose a different query, it changes selection, not mailbox state. A message-limit notice means there may be unprocessed matching mail; narrow the window or increase the limit and rerun. The workbook deduplicates previously stored identities. The tool does not create filters/labels or change read/unread, archive or deletion state.

## 7. Create your own Google project and Desktop authorization

These are user-operated steps. GitHub publication and Google's OAuth app publishing/verification are separate processes. This repository contains no shared OAuth client.

1. Create/select your own project in the [Google Cloud console](https://console.cloud.google.com/) using the [project guide](https://developers.google.com/workspace/guides/create-project). Keep the correct project selected throughout setup.
2. Enable **Gmail API** in the API library, as described by the [Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python).
3. Configure **Google Auth platform → Branding** using the [consent guide](https://developers.google.com/workspace/guides/configure-oauth-consent). Supply your own app/support/contact information. For a personal Gmail account, use **External**, not an organization-only Internal audience. Keep testing limited to your own account; under **Audience → Test users**, add that account. Existing projects can show Branding, Audience and Data Access directly.
4. Under **Data Access**, add only `https://www.googleapis.com/auth/gmail.readonly`. It is a **restricted** scope. It permits reading messages/settings broadly; labels/query do not restrict the grant itself. Metadata-only scope cannot supply message bodies, so it cannot replace this scope for these parsers. See [Google's scope definitions](https://developers.google.com/workspace/gmail/api/auth/scopes).
5. In **Google Auth platform → Clients**, create an OAuth client with application type **Desktop app**, name it for your own use, and download its JSON, following the quickstart. Do not choose a web/service-account client or add unrelated scopes. Desktop authorization opens the system browser and uses a local callback; see [Google's desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).
6. Create `.local` in this project and save your downloaded file there as **oauth-client.json**. Keep the whole folder private. The tool accepts Google Desktop client endpoints, not edited third-party authorization URLs.

Scope/verification requirements depend on Google's policies and audience. This project has not passed Google verification and does not promise exemption. Review Google's linked scope/consent guidance before broader distribution. For an External app in **Testing**, Google documents refresh-token expiry after seven days for scopes such as Gmail read-only; see [token expiration](https://developers.google.com/identity/protocols/oauth2#expiration). Account revocation, inactivity, password/policy changes and token limits can also invalidate authorization. Do not assume it will work unattended forever.

## 8. Prepare private live files and authorize explicitly

Install the optional libraries in the same environment:

```powershell
.\.venv-win\Scripts\python.exe -m pip install -r requirements-live.txt -c constraints.txt
New-Item -ItemType Directory -Force .local | Out-Null
if (Test-Path live.toml) {
    Write-Host "Keeping existing live.toml."
} else {
    Copy-Item live.example.toml live.toml
}
notepad live.toml
```

Confirm `label` is your label, adjust `query` if needed, and begin with `max_messages = 10`. All six settings are required and unknown settings fail. OAuth client/token/output paths must be distinct and inside this project's `.local` directory. The personal preferences file stays ignored at project root. Original-project paths and symlink escapes are rejected.

Ensure `.local/oauth-client.json` is your newly downloaded Desktop JSON, then run:

```powershell
.\.venv-win\Scripts\python.exe -m job_monitor live --settings live.toml --preferences preferences.txt --authorize
```

Select the intended dedicated account in the browser and inspect the app/project and requested permission. Continue only for your own expected client and access; stop for an unexpected app, scope or policy message. An unverified-app warning is not proof of trust. This CLI does not print the consent URL, authorization code or tokens. If no browser/callback is available, authorization fails with an English message; remote/headless authorization workarounds are not implemented.

The SDK stores access/refresh information in the configured local token file, atomically and with restrictive POSIX file modes where supported. Windows folder permissions still depend on your account/ACLs; do not store private files in a shared or synced public folder. The app never asks for your Google password. No token exists in the public file set. If you omit `--authorize` with no token, the program stops rather than opening consent implicitly.

## 9. Read and maintain the spreadsheet

The sheets are:

- **Opportunities:** newly matched Strong/Good/Consider rows and existing review history.
- **Discarded:** below-threshold or explicitly Excluded rows. Excluded may retain a positive score; inspect the explanation.
- **Latest run:** the last batch that added rows, sorted by score. A no-new-items run preserves that snapshot; the CLI states the counts for the current run.

The hidden Key column stores platform plus canonical URL. Do not edit it, rename/reorder sheets or change headers. Status is a dropdown (New, Review, To apply, Applied, Discarded). Edit Status, Applied date and Notes in the main two sheets; Latest run is a separate snapshot. Setting Discarded status does not automatically move a row between sheets. Historical scores and explanations do not silently change when preferences change.

Reruns compare identities in both main sheets, including jobs discarded earlier. Same-link updates are skipped rather than merged. Cleanup removes `utm_*`, `fbclid`, `gclid` and `msclkid`, normalizes supported host aliases and drops URL fragments. Other raw query parameters, their encoding/order, path case and identifiers remain. Distinct meaningful parameters remain distinct identities; reordered unknown parameters can also remain distinct. Redirect-wrapped/unrecognized links are not fetched and may be skipped. Check the preserved links manually before following them.

Email text is stored as literal strings, not formulas, including leading `=`, `+`, `-`, `@` or tabs. Recognized HTTPS project links alone become hyperlinks. Very long extracted fields are clipped to 30,000 characters with a diagnostic; missing optional budget/description fields are retained with notices. Title/link are required.

Close the workbook before each run. A monitor lock prevents overlapping writers. A temporary workbook is validated before atomic replacement; detected concurrent changes, Excel owner files, write failures or Windows locks prevent replacement. A simulated locked-file failure is tested; native Excel locking still needs your review. On systems that allow replacement of an open file, close the editor anyway to prevent it saving stale data later. Preserve private backups of live output yourself; no automatic backup or retention service is implemented.

## 10. Daily operation and updates

With a valid token, run the same live command **without** `--authorize`. An expired token may refresh over the network. Revoked/invalid authorization fails safely; no stored token is silently deleted and no fresh consent is opened after a refresh failure.

Run manually, review the generic counts/notices, then open the workbook. New/no-new counts describe additions, not a guarantee that every matching message was read. An empty configured window may legitimately add nothing. There is no automatic scheduling implementation or verified Task Scheduler/cron setup.

Before updating code, close Excel, preserve private backups outside publication, and retain your own preferences/live settings separately. Review release changes and reinstall using the appropriate requirement file plus constraints in your own environment. Do not replace your configuration with the example or reuse someone else's token. The tool refuses an unrelated workbook or a demo/live mode mismatch. Schema migration of older/private workbooks is not implemented: choose a fresh output and retain the old file privately.

## 11. Troubleshooting and revocation

| Symptom | Action |
|---|---|
| Python/venv missing | Verify Python 3.12 in a new terminal and use the official installation guide. Use the environment's full interpreter path, not an unrelated global pip. |
| Preferences line error | Inspect that line locally; check separators, duplicate normalized rules, full-line comments and thresholds. Do not paste personal preferences into an issue. |
| Label missing/ambiguous | Check the manual label name and nested-label path. The tool requires one case-insensitive match and never creates a label. |
| No new rows | Check live label/query, limit notice, existing duplicates and filters. Repeated reads of stored jobs intentionally add nothing. |
| `unexpected_99freelas_template` / `unexpected_freelancer_template` | The mail lacks the supported structure. Inspect it privately; do not upload it. Report only an invented minimal reproduction. |
| `unsupported_sender` | The From domain is not the expected platform/domain for this mode; verify the authentic alert locally. Fixture .example senders are offline-only. |
| `missing_title` / `missing_or_invalid_link` | The item is skipped. Wrapped, non-HTTPS or foreign links are not followed. |
| `missing_budget` / `missing_description` / `truncated_field` | Item retained with incomplete/clipped data; review it locally before deciding. |
| `malformed_email` | A MIME payload/encoding is unsupported or too large. Attachments are not downloaded. |
| Authorization/client error | Confirm your own enabled Gmail project, External test user and Desktop JSON. Never paste token/client files into support chats. |
| Refresh failed/revoked | Use Google's access-management page below; remove/revoke the old grant as appropriate, then remove your local token and run live --authorize again. The app does not delete it for you. |
| Workbook locked/write failure | Close Excel and other monitor runs. Check permissions/disk space. Preserve the workbook; inspect a stale `.lock` locally before removing it when no run remains. |

To revoke access, use your [Google Account's linked-app access controls](https://support.google.com/accounts/answer/13533235): select the relevant app's access to your Google Account, review details, remove access and confirm. Removing a Sign in with Google link alone is not necessarily the same as removing the data-access grant. Delete your local token only after understanding which grant it represents. A later live run will require fresh consent. Local workbooks remain on disk after revocation; manage those copies separately. Do not share them publicly.

## 12. Safe issue reports and contributions

Include Python/project versions, mode, generic error text and a reproduction using the included demo or newly invented mail. Never attach OAuth JSON, browser URLs/codes, tokens, Gmail IDs, screenshots of personal mail, original alerts, live workbooks, logs with payloads, or personal preferences. The repository ignores common private/runtime paths, but inspect every file before sharing.

Tests use generated fixtures and mocked Gmail/OAuth responses. Install `requirements-dev.txt`, then run `python -m pytest -q` using the project interpreter. No test authorizes an account or needs network access. If adding a parser, create original fictional examples; do not copy a customer's email or vendor artwork. Preserve dependency notices and ensure you have redistribution rights for contributions. No application license or authorship claim is assigned automatically.
