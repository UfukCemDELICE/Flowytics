# Frontend

## Scope

The web frontend exists ONLY for onboarding. No web dashboard, no analytics pages, no report viewer. After onboarding, the user closes the browser and uses Slack exclusively.

If customer feedback repeatedly requests a web dashboard post-launch, revisit this decision.

## Design Source of Truth

The existing frontend design (built with Google Stitch, refined in Antigravity) on `main` branch is the design source of truth. All new components and pages must match this established visual language.

**Rules:**
- Do NOT override existing component styles, color palette, spacing, or typography.
- New pages (e.g., onboarding steps) must use the same design tokens and patterns as existing pages.
- Before modifying any existing component, review the current implementation and preserve its visual design.
- If a design change is needed, discuss with the founder first — don't silently alter the look and feel.
- shadcn/ui components must be themed to match the existing design, not used with defaults.

## Tech Stack

- Next.js (App Router, TypeScript strict mode)
- Tailwind CSS + shadcn/ui (Zinc theme, dark mode)
- Clerk (`@clerk/nextjs`) for auth
- Stripe (`@stripe/stripe-js`) for payment
- Codat Link SDK for accounting connection
- Plaid Link (`react-plaid-link`) for banking connection
- Thin `fetch` wrapper for backend API calls (no axios, no supabase-js)

## Page Structure

```
frontend/src/app/
├── page.tsx                    # Landing → redirect to /onboarding or marketing
├── sign-in/[[...sign-in]]/
│   └── page.tsx                # Clerk Sign In
├── sign-up/[[...sign-up]]/
│   └── page.tsx                # Clerk Sign Up
├── onboarding/
│   ├── layout.tsx              # Stepper layout (progress bar across top)
│   ├── page.tsx                # Step router (redirects to current step)
│   ├── payment/page.tsx        # Step 1: Stripe payment setup
│   ├── accounting/page.tsx     # Step 2: Connect QBO/Xero via Codat
│   ├── banking/page.tsx        # Step 3: Connect bank via Plaid (skippable)
│   ├── slack/page.tsx          # Step 4: Connect Slack workspace
│   └── done/page.tsx           # Step 5: Success — "Go to Slack"
├── settings/
│   └── page.tsx                # Manage connections (reconnect, disconnect)
└── layout.tsx                  # Root layout (Clerk provider, global styles)
```

## Onboarding Flow

### Step 1 — Payment (Stripe)

User enters payment info. 14-day free trial, $150/mo after.

**Implementation:**
- Backend creates a Stripe Checkout Session with `mode: "subscription"`, `trial_period_days: 14`
- Frontend redirects to Stripe Checkout (hosted page)
- On success, Stripe redirects back to `/onboarding/accounting`
- Stripe webhook `checkout.session.completed` → backend creates tenant record, links `stripe_customer_id`

**Trial start:** `trial_started_at` is set NOT on payment setup, but when the first analysis runs successfully. The 14-day clock starts from first value delivered.

**Why payment before connections:** Filters for serious intent. Only founders willing to commit (even with free trial) go through the integration steps. Reduces tire-kicker load on Codat/Plaid API quotas.

### Step 2 — Connect Accounting Software (Codat)

User connects QBO, Xero, or other supported accounting software.

**Implementation:**
- Backend calls Codat API to create a company → receives `companyId`
- Backend generates Codat Link URL for that company
- Frontend opens Codat Link in embedded iframe or redirect
- User authorizes in QBO/Xero OAuth flow
- Codat webhook `dataConnectionStatusChanged` → backend saves integration record
- Frontend polls backend until connection confirmed → advance to next step

**UI:**
- Show list of supported platforms (QBO, Xero) with logos
- "Connect" button launches Codat Link
- Loading state while waiting for authorization
- Green checkmark when connected
- Error state with "Try Again" button

### Step 3 — Connect Bank (Plaid) — OPTIONAL

User connects bank account for real-time cash data.

**Implementation:**
- Backend calls Plaid `/link/token/create` → receives `link_token`
- Frontend initializes Plaid Link with `link_token`
- User selects bank and authorizes
- Plaid returns `public_token` → frontend sends to backend
- Backend exchanges `public_token` for `access_token` → saves integration record
- Frontend advances to next step

**UI:**
- Clear messaging: "Optional — connect for real-time cash tracking"
- Prominent "Skip" button alongside "Connect Bank"
- Same pattern: loading → connected → next

**Why optional:** Codat already provides bank data from QBO's connected bank feeds. Plaid adds real-time balance (hours vs minutes stale). Not critical path for MVP value.

### Step 4 — Connect Slack

User adds Flowytics bot to their Slack workspace.

**Implementation:**
- "Add to Slack" button using Slack OAuth V2 URL
- Scopes: `chat:write`, `channels:manage`, `im:write`, `app_mentions:read`, `commands`
- On callback: backend receives `access_token` + `team_id`
- Backend saves to tenant record (`slack_team_id`)
- Bot creates or identifies `#flowytics-cfo` channel
- Backend saves `slack_channel_id`
- Initial welcome message sent to channel

**UI:**
- Standard Slack "Add to Slack" button (use official SVG)
- After authorization: show connected workspace name
- "Connected to {workspace}" with green checkmark

### Step 5 — Done

Onboarding complete. Direct user to Slack.

**UI:**
```
✅ You're all set!

Your CFO intelligence is being set up. Here's what happens next:

1. We're analyzing your financial data right now
2. Your first CFO briefing will arrive in Slack within 24 hours
3. Ask me anything in #flowytics-cfo — I'm always available

[Open Slack →]
```

**Backend trigger:** On reaching this step, backend dispatches initial data sync + first analysis as a background task.

## Clerk Integration

### Middleware

```typescript
// frontend/middleware.ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)"]);

export default clerkMiddleware(async (auth, req) => {
    if (!isPublicRoute(req)) {
        await auth.protect();
    }
});

export const config = {
    matcher: ["/((?!.*\\..*|_next).*)", "/", "/(api|trpc)(.*)"],
};
```

### API Calls to Backend

```typescript
// frontend/src/lib/api.ts
import { auth } from "@clerk/nextjs/server";

export async function api(path: string, options: RequestInit = {}) {
    const { getToken } = await auth();
    const token = await getToken();

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
            ...options.headers,
        },
    });

    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}
```

All frontend-to-backend communication goes through this wrapper. No direct Supabase access from frontend.

## Settings Page

Minimal. Shows:
- Connected accounting software (with "Reconnect" and "Disconnect" buttons)
- Connected bank (if any)
- Connected Slack workspace
- Subscription status (links to Stripe Customer Portal for management)

No analytics, no charts, no reports. Those are in Slack.

## Design Conventions

- **Theme:** Dark mode, Zinc palette (matches Figma design)
- **Components:** shadcn/ui exclusively. No custom component library.
- **Layout:** Max-width container (1280px), centered
- **Spacing:** Tailwind spacing scale, consistent padding
- **Typography:** System font stack via Tailwind defaults
- **Loading states:** Skeleton components from shadcn/ui
- **Error states:** Toast notifications from shadcn/ui
- **Responsive:** Desktop-first. Onboarding works on mobile but not optimized.
