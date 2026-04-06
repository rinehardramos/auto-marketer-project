# Data model

Auto Marketer stores its state in PostgreSQL. Research data is consumed from the sibling `info-broker` service and is not stored permanently in the marketing database except within the context of email drafts.

## PostgreSQL schema

The database (`auto_marketer` by default) contains two primary tables. All writes use parameterized SQL to prevent injection.

### `campaigns`

Defines a set of outreach efforts with a specific goal and tone.

| Column | Type | Meaning |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Internal identifier. |
| `name` | `VARCHAR` | Human-readable name (e.g., "Q2 SMB Push"). |
| `tone` | `VARCHAR` | The desired voice (e.g., "professional", "warm", "casual"). |
| `goal` | `TEXT` | The objective (e.g., "book a 15-min discovery call"). |
| `status` | `VARCHAR` | `draft`, `active`, or `completed`. |
| `created_at` | `TIMESTAMP` | When the campaign was initialized. |

### `email_drafts`

Individual emails generated for specific prospects within a campaign.

| Column | Type | Meaning |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Internal identifier. |
| `campaign_id` | `INT` | Foreign key to `campaigns(id)`. |
| `profile_id` | `VARCHAR` | The `info-broker` profile identifier. |
| `recipient_email`| `VARCHAR` | Target email address. |
| `recipient_name` | `VARCHAR` | Target person's name. |
| `subject` | `TEXT` | LLM-generated subject line. |
| `body` | `TEXT` | LLM-generated email body. |
| `status` | `VARCHAR` | `draft`, `sent`, or `failed`. |
| `sent_at` | `TIMESTAMP` | When the email was successfully sent. |
| `error_message` | `TEXT` | Detailed failure reason if `status` is `failed`. |
| `provider_message_id` | `VARCHAR` | Identifier from the sender provider (SMTP/API). |

## Integration with info-broker

`auto-marketer` does not maintain its own copy of prospect profiles. Instead:
1. It requests profiles from `info-broker/profiles`.
2. It uses the `profile_id` to link drafts to their source.
3. The `recipient_email` and `recipient_name` are cached in `email_drafts` at generation time to ensure the draft remains valid even if the source profile changes or is deleted in the broker.
