---
name: DiaCare AI
description: A restrained, evidence-first workspace in navy, blue, and clear reading surfaces.
colors:
  primary: "#2563EB"
  primary-hover: "#1D4ED8"
  primary-ink: "#174AA8"
  navy: "#0B1F3A"
  nav-ink: "#EEF4FC"
  nav-muted: "#C2D0E2"
  ground: "#F0F4FA"
  surface: "#FFFFFF"
  surface-soft: "#F7F9FC"
  surface-secondary: "#E8EFF9"
  ink: "#172B4D"
  body: "#2E4564"
  muted: "#52657F"
  line: "#DCE5F0"
  line-soft: "#E8EFF9"
  line-strong: "#BDCDE1"
  neutral: "#53647B"
  success: "#16845B"
  success-ink: "#116746"
  success-soft: "#E8F5EE"
  warning: "#704800"
  warning-line: "#DFC27B"
  warning-soft: "#FFF7E8"
  danger: "#DC4545"
  danger-ink: "#A52D35"
  danger-soft: "#FFF1F1"
  danger-line: "#E8B1B1"
typography:
  headline:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "25px"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 650
    lineHeight: 1.55
  body:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.45
rounded:
  tag: "5px"
  control: "8px"
  composer: "10px"
  surface: "12px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "42px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-outline:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "42px"
  input-composer:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.composer}"
    padding: "7px 7px 7px 13px"
  nav-item:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.nav-ink}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "46px"
  synthetic-tag:
    backgroundColor: "{colors.surface-secondary}"
    textColor: "#173C76"
    rounded: "{rounded.tag}"
    padding: "4px 7px"
  reading-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "12px 14px"
  evidence-disclosure:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "0"
    padding: "0 5px"
    height: "43px"
---

# Design System: DiaCare AI

## Overview

**Creative North Star: "Clinic Record · Evidence Rail"**

DiaCare AI pairs a firm navy navigation spine with a cool, pale work ground and white reading surfaces. Blue marks actions and evidence; green, amber, and red communicate system and safety states. The clinic-record influence is orderly and legible, while the visual treatment stays clearly within a course prototype.

The conversation is the primary work surface. Long answers keep a readable measure, and trace rows and citations follow each answer as compact disclosures. Synthetic profile history remains reachable from the same shell. The interface uses Be Vietnam Pro and a single Lucide icon family, with flat surfaces doing most of the visual work.

**Key Characteristics:**
- Navy navigation anchors the work area.
- A flexible conversation column carries the main reading task.
- Trace rows and sources stay compact until opened; the desktop rail keeps system status and tools visible.
- Live health data controls readiness labels and approved-source counts.

## Colors

The palette uses deep blue for navigation, clear blue for action, pale blue-gray for working surfaces, and high-contrast ink for long-form reading.

### Primary
- **Clear Action Blue:** Primary actions, links, selected navigation marks, and chart data use this color family.
- **Deep Reading Blue:** Darker blue supports emphasized links, icons, and focus cues.
- **Navigation Navy:** The left navigation uses a deep navy field with light text; the working canvas remains light.

### Secondary
- **Success Green:** Reserved for available or successful states.
- **Safety Amber:** Identifies caution, unreviewed web results, and pending or unknown states.
- **Emergency Red:** Reserved for emergency and error states.

### Neutral
- **Workspace Mist:** The page ground separates work regions without competing with content.
- **Paper White and Soft White:** Reading surfaces stay white; answer bubbles use a quieter near-white surface.
- **Pale Evidence Blue:** Marks selected states, synthetic labels, and informational notices.
- **Deep Ink, Body Ink, and Muted Slate:** Primary text, supporting text, and low-priority labels use progressively quieter blue-tinted values.
- **Fine, Soft, and Strong Rules:** Dividers and control outlines organize the interface without heavy borders.

**The Semantic-State Rule.** Use green, amber, and red only for their corresponding readiness, caution, or emergency meanings.

## Typography

**Display Font:** Be Vietnam Pro, with a system sans-serif fallback.  
**Body Font:** Be Vietnam Pro, with a system sans-serif fallback.  
**Label/Mono Font:** Labels use the same family; measurements use tabular numerals rather than a separate mono face.

**Character:** Compact, steady sans-serif lettering keeps Vietnamese diacritics and measurement values clear. Weight changes establish hierarchy without relying on display typography.

### Hierarchy
- **Headline** (700, 25px, 1.25 line-height): The history page heading.
- **Section heading** (650, 18px, 1.35 line-height): Markdown answer headings and prominent panel labels.
- **Title** (600–700, 15–16px): Conversation identity, profile name, and reading-section titles.
- **Body** (400, 15px, 1.55 default line-height; answer copy 1.68): Long-form messages and supporting descriptions, capped at about 72ch for message text.
- **Label** (500–700, 10–13px): Metadata, trace status, chips, and compact controls.

**The Measurement Rule.** Keep displayed measurements and profile numbers in tabular numerals so values scan cleanly.

## Layout

At desktop widths (1280px and above), a fixed 248px navigation rail sits beside a flexible conversation and a 268–304px system rail. A 20px column gap and modest workspace insets keep the three regions distinct. The message column holds answer text to about 72ch; long history content scrolls within the content region.

At widths up to 1279px, navigation becomes a 76px icon rail and the system rail moves into an on-demand side panel up to 340px wide. The panel has a close control and a scrim; the header exposes its toggle.

At widths up to 767px, the shell becomes a single column. The brand bar is 58px high, navigation opens as a drawer, profile and emergency controls wrap into the header, and the system rail remains optional. Suggestions stack vertically and the composer remains attached to the conversation. At 420px and below, the status toggle becomes icon-only while retaining its accessible name.

At widths up to 900px, header and workspace insets tighten. On short desktop viewports (720px high or less), vertical padding and conversation header spacing reduce. Chat messages scroll inside the conversation; history scrolls in its content region. Tables keep their own horizontal scroll area.

**The Readable-Measure Rule.** Keep long answer text near its current 72ch maximum; give tables a local scroll area rather than widening the page.

## Elevation & Depth

Resting surfaces stay flat, organized by tonal contrast and thin rules. Offset, soft shadows are reserved for the system drawer and emergency dialog. Focus feedback is functional: interactive controls use a visible outline, while the composer wrapper changes border and adds a small focus ring.

### Shadow Vocabulary
- **Side panel:** 0 12px 32px rgb(11 31 58 / 18%) — separates the optional rail from the work area.
- **Emergency dialog:** 0 14px 38px rgb(11 31 58 / 24%) — gives the urgent action surface clear separation.

**The Flat-at-Rest Rule.** Keep ordinary reading and status surfaces free of elevation; use dividers and surface tone to group them.

## Shapes

Controls use gently rounded corners. The composer has a slightly softer outline than buttons; reading surfaces have the broadest corners. Message bubbles use an asymmetric corner to distinguish conversational turns. Tables and trace rows use separators instead of card shells.

**The One-Surface Rule.** Do not place same-level cards inside another card; use a surface, a divider, or whitespace to establish hierarchy.

## Components

### Buttons
Primary send and emergency actions use solid semantic colors, compact horizontal padding, and a 42px minimum height. Primary buttons darken on hover and use the global visible focus outline. Disabled send buttons switch to a muted neutral state. Secondary controls such as the system toggle use a white background and a thin strong-rule outline.

### Chips
Synthetic-data labels use a pale blue surface, dark blue text, and compact corners. Readiness states use colored text and icons so state is not communicated by color alone.

### Cards / Containers
The conversation container is a white, lightly bordered reading surface. The profile summary uses a restrained border and internal padding. Status rows and metrics remain flat, separated by rules rather than nested cards.

### Inputs / Fields
The message composer pairs a white field with a quiet border and a compact send action. The textarea grows with content, then scrolls at its maximum height. Focus changes the wrapper border and adds a blue ring. On mobile, suggestions become full-width rows and the composer keeps a 42px minimum control height.

### Navigation
Desktop navigation is a full-width navy rail with text labels; the active row has a tonal blue background and a small marker. Tablet navigation becomes icon-only. Mobile navigation appears in a left drawer with a scrim and explicit close control. The skip link appears on keyboard focus.

### Evidence and citations
Trace and tool calls use native disclosure rows with compact counts. Citations remain adjacent to the answer; a source is clickable only when it has an HTTPS URL. Missing URLs render as static references.

**The Evidence-After-Answer Rule.** Keep trace and sources after the answer as compact disclosures; leave them collapsed until requested.

### History and measurements
The history surface uses a small metric row, a responsive glucose chart, and a table that scrolls inside its own container. Numeric readings use tabular figures. Synthetic data labels stay visible near the profile summary.

## Do's and Don'ts

### Do:
- **Do** keep the conversation, trace, and source order intact so answers remain readable and auditable.
- **Do** preserve the light reading ground, navy navigation, semantic actions, and blue-tinted dividers.
- **Do** keep safety and synthetic-data notices visible above the chat.
- **Do** show system readiness and source counts only from data supplied by the health response.
- **Do** use tabular numerals for measurements and allow long tables to scroll inside their container.

### Don't:
- **Don't** add gradients, decorative glow, or glass surfaces.
- **Don't** nest decorative cards or wrap every section in a rounded tile.
- **Don't** present missing model artifacts, citations, or system results as ready.
- **Don't** turn long medical explanations into compressed dashboard copy.
