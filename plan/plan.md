# Gig Builder: Full Fiverr Gig Setups Built to Rank

Turns any scanned keyword into a complete, ready-to-paste Fiverr gig: title, tags, description, three pricing packages, FAQ, buyer requirements and gallery image file names.
Every section is written from real scan data (top gigs, prices, related keywords) to rank on page one.

## Who it's for
- Fiverr sellers who want to launch a new gig in an underserved niche found by the dashboard.
- Existing sellers rewriting a gig that doesn't rank.

## Core features and experience
- **Build from a scan**: pick any keyword already scanned (or a "Gold" niche) and click "Build Gig". The setup uses that keyword's top gigs, prices, autocomplete phrases and keyword proximity data.
- **Ranking-first title**: written after the fixed "I will" prefix, at most 80 characters. It is a dense keyword string that still reads sensibly, not a polished sentence. Example: `I will` + `design minimalist logo, modern business logo, brand identity logo design`. The main keyword goes first, then long-tail variants. A live character counter shows the count (for example 74/80). Three title options are given, ranked by keyword coverage.
- **Search tags**: 5 tags (Fiverr's maximum), each 20 characters or fewer, taken from the strongest autocomplete and proximity keywords. No tag repeats a title word exactly unless it is a high-volume phrase.
- **Description**: up to 1,200 characters. The main keyword appears in the first sentence, secondary keywords appear naturally, and it uses Fiverr-safe formatting (short sections, bullet points, a call to action). Contact details and off-platform words are never used. Shows a character counter.
- **Three pricing packages (Basic / Standard / Premium)**: each has a package name, a short description, a delivery time, revisions, included extras and a price. Prices are based on what top gigs in the niche charge: Basic is just under the niche median to win clicks, Standard sits at the median, and Premium is near the top range. Two or three optional gig extras (for example fast delivery) are suggested.
- **FAQ**: 5 to 8 question-and-answer pairs that use keywords and answer common buyer doubts.
- **Buyer requirements**: 3 to 5 questions the buyer answers after ordering, each marked as free text, multiple choice or file upload.
- **Gallery image file names**: 3 file names made of ranking keywords joined by "-". Example: `minimalist-logo-design-modern-business-logo.jpg`. Each comes with a short note on what that image should show.
- **Category and subcategory**: a suggested Fiverr category, subcategory and service type that match the keyword.
- **Ranking checklist**: a score showing which ranking rules each section meets, such as main keyword in title, tags within limits and description length.
- **Copy buttons**: one-click copy for every section and every single tag, package or FAQ item.
- **Regenerate one section**: refresh only the titles, only the tags, only the pricing and so on, without changing the rest.
- **History**: every setup is saved and can be reopened, edited or deleted.
- **Download**: export the whole setup as one Word document, laid out in the same order as Fiverr's gig creation steps.

## Access
- **Pro and admin users** get the full setup.
- **Free users** see a preview with the title options and tags. The rest (description, pricing, FAQ, requirements, images) is blurred and shows an "Upgrade to Pro" button that leads to the existing checkout.
- Building a gig setup does not use scan credits.

## User flow
1. The user scans a keyword on the dashboard as usual, or opens an existing niche.
2. They click "Build Gig" on a niche row or on the AI panel.
3. A progress state shows while the setup is written (about 10 to 20 seconds).
4. The setup opens in sections that follow Fiverr's creation order: Overview (title, category, tags), Pricing, Description and FAQ, Requirements, Gallery.
5. The user copies sections, regenerates any section they don't like, or downloads the document.
6. The setup is saved automatically to "My Gig Setups", which they can open from the dashboard header.

## UI/UX feel
- Same Swiss high-contrast look as the dashboard: Cabinet Grotesk headings, IBM Plex Mono for counters, tags and file names, sharp edges and strong black/white contrast with gold accents for top-ranked items.
- The fixed "I will" prefix sits in grey before each editable title so the 80-character limit is always visible.
- Character counters turn red when a section goes over a limit.

## Implementation phases
**Phase 1 — MVP (built now)**
- Build Gig from a scanned keyword with all the sections listed above, the ranking checklist, Pro/free access rules, copy buttons, regenerating one section, saved history and Word download.

**Phase 2**
- Compare a setup side by side with the top 3 ranking gigs for that keyword.
- Inline editing with the ranking checklist updating live as you type.

**Phase 3**
- Gig Audit: paste an existing gig's link or text and get a rewritten, better-ranking version.
- Generated gallery images that match the suggested file names.

## Assumptions
- Setups are written by the app's current AI (Gemini 3 Flash). Claude is not used, as requested.
- A keyword must be scanned first. If its scan is older than 7 days, the user is asked to rescan, but can still build from the old data.
- Fiverr limits used: title of 80 characters after "I will", 5 tags of 20 characters or fewer each, description of 1,200 characters, package name of 35 characters, package description of 100 characters, minimum price of $5, and 3 gallery images.
- Prices are shown in USD and rounded to Fiverr-style amounts (for example $15, $45, $120).
- All text is in English.
- Download format is Word (.docx).
- Regenerating a section has no limit for Pro users.
