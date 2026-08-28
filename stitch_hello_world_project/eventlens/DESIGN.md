---
name: EventLens
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#7bd0ff'
  on-secondary: '#00354a'
  secondary-container: '#00a6e0'
  on-secondary-container: '#00374d'
  tertiary: '#ffafd3'
  on-tertiary: '#620040'
  tertiary-container: '#e364a7'
  on-tertiary-container: '#560038'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#c4e7ff'
  secondary-fixed-dim: '#7bd0ff'
  on-secondary-fixed: '#001e2c'
  on-secondary-fixed-variant: '#004c69'
  tertiary-fixed: '#ffd8e7'
  tertiary-fixed-dim: '#ffafd3'
  on-tertiary-fixed: '#3d0026'
  on-tertiary-fixed-variant: '#85145a'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The design system embodies a "High-Tech Minimalist" aesthetic, tailored for a premium, privacy-conscious audience. It focuses on clarity, technical precision, and a focused user experience. The visual language is defined by deep spatial depth, utilizing dark surfaces to reduce eye strain and emphasize critical information.

The design style leans into **Glassmorphism** and **Modern Corporate** influences. It utilizes semi-transparent layers and background blurs to create a sense of lightness and sophisticated hierarchy without clutter. The emotional response should be one of "effortless control"—where the interface feels like a high-performance instrument that respects user data and professional workflows.

## Colors

The palette is anchored by a "Deep Slate" foundation to provide a rich, expansive canvas for high-contrast accents. 

- **Primary (Indigo/Violet):** Used for primary actions, active states, and brand-critical indicators.
- **Secondary (Sky Blue):** Utilized for secondary data visualizations or informational highlights.
- **Neutral (Deep Slate):** The core background color.
- **Surface:** A slightly lighter slate used for containers, cards, and navigation elements.
- **Borders:** Subtle white opacity (`rgba(255,255,255,0.1)`) is used exclusively to define edges on glassmorphic surfaces, ensuring a premium feel without harsh lines.

## Typography

This design system uses a dual-font strategy to balance character with utility. **Plus Jakarta Sans** provides a modern, approachable feel for headlines and large display text, while **Inter** ensures maximum legibility for body copy and technical data.

High contrast is achieved through varied font weights and deliberate scale jumps. Large titles should use tighter letter spacing to maintain a "locked-in" professional appearance. Small labels and metadata should use increased letter spacing and uppercase styling to denote a technical, data-driven context.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a focus on generous negative space to emphasize the minimalist aesthetic.

- **Desktop:** 12-column grid with a 24px gutter. Content is centered with a max-width of 1440px.
- **Tablet:** 8-column grid with a 20px gutter.
- **Mobile:** 4-column grid with 16px margins.

Spacing follows a strict 8px/4px geometric scale. Internal card padding should be consistently set to `md` (24px) for desktop and `sm` (16px) for mobile to ensure a comfortable breathing room for content.

## Elevation & Depth

Hierarchy is established through **Glassmorphism** and **Tonal Layering** rather than traditional heavy shadows.

- **Level 0 (Background):** Deep Slate (#0F172A).
- **Level 1 (Surfaces):** Surface Slate (#1E293B) with no blur, used for sidebars and base content containers.
- **Level 2 (Modals/Overlays):** Glassmorphic panels with `backdrop-filter: blur(12px)` and a 1px `white/10` border.
- **Shadows:** Use extremely soft, large-radius indigo-tinted shadows (`rgba(99, 102, 241, 0.05)`) only for high-priority elements like floating action buttons to simulate an "inner glow" or "light leak" effect.

## Shapes

The design system utilizes "Rounded" (0.5rem) corners for small utility elements, but shifts to larger, softer radii for major containers to achieve a "premium tech" feel.

- **Small Components (Inputs/Chips):** 8px (0.5rem).
- **Cards & Primary Containers:** 16px (1rem).
- **Large Sections/Modals (2xl):** 24px (1.5rem).
- **Buttons:** Fully rounded (pill) for action-oriented visuals or 12px for integrated layouts.

## Components

### Buttons
- **Primary:** Solid Indigo gradient background with white text. High-vibrancy.
- **Secondary:** Transparent background with a `white/10` border and `backdrop-filter`.
- **Tertiary/Ghost:** No background or border, Indigo text.

### Inputs
Fields should use the `Surface` color with a subtle `white/5` fill. On focus, the border transitions to Primary Indigo with a soft 4px outer glow. Labels should use the `label-caps` typography style for a technical feel.

### Cards
Cards are the primary container unit. They must feature a subtle `white/10` top-edge highlight and a 1px border. Backgrounds should be semi-transparent when layered over other elements to activate the backdrop-blur effect.

### Chips & Tags
Small, 8px rounded elements with a `white/5` background. Status-specific chips (e.g., "Active", "Private") use low-opacity versions of the semantic colors (Indigo, Green, or Red) for the background with high-contrast text.

### Privacy Indicators
Unique to this design system, privacy-conscious status icons (e.g., "End-to-End Encrypted") should be persistently visible in navigation bars or headers using a subtle secondary-color tint.