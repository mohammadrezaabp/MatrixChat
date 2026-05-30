# Matrix Chat - Visual Guide

## UI Layout

```
╔════════════════════════════════════════════════════════════╗
║  MATRIX CHAT                                               ║
║  > Connected to Llama 3.2 via local Ollama instance       ║
║══════════════════════════════════════════════════════════║
║                                                            ║
║  ┌──────────────────────────────┐                         ║
║  │ $ [SYSTEM INITIALIZED]       │                         ║
║  │ WELCOME TO MATRIX CHAT v1.0  │  ← Assistant Message    ║
║  │ Connected to: Llama 3.2      │   (Green borders,       ║
║  │ Status: ONLINE               │    Secondary color)     ║
║  │ Type your message...         │                         ║
║  └──────────────────────────────┘                         ║
║  LLAMA                                                    ║
║                                                            ║
║                                                            ║
║                      (message area)                        ║
║                                                            ║
║                                                            ║
║                            ┌──────────────────────┐        ║
║                            │ > What is AI?        │        ║
║                            │ (Primary color)      │        ║
║                            └──────────────────────┘        ║
║                                             USER           ║
║                                                            ║
║══════════════════════════════════════════════════════════║
║  > ENTER YOUR QUERY...                              SEND   ║
║  PRESS ENTER TO SEND | SHIFT+ENTER FOR NEW LINE          ║
╚════════════════════════════════════════════════════════════╝
```

## Color Reference

### Primary Color: Bright Green (#00FF00)
- Title "MATRIX CHAT"
- User messages
- Input field text
- Button when focused
- Primary borders

```
████████████████ #00FF00 - User messages and primary UI
```

### Secondary Color: Medium Green (#00CC00)
- Assistant messages
- Secondary text elements
- Accent borders

```
████████████████ #00CC00 - Assistant messages
```

### Background: Black (#000000)
- Entire page background
- Message bubbles background
- Input field background (slightly darker)

```
████████████████ #000000 - Pure black background
```

### Muted Green (#003300)
- Borders
- Disabled text
- Secondary information

```
████████████████ #003300 - Borders and disabled states
```

## Typography

### Font Family
- **Font**: Monospace (Geist Mono / system monospace)
- **Why**: Terminal/Matrix aesthetic

### Font Sizes
```
Title:        24px (2xl)
Message Text: 14px (sm) to 16px (base)
Labels:       12px (xs)
Helpers:      12px (xs)
Input:        14px (sm)
```

### Font Weights
- Headers: Bold (700)
- Body: Regular (400)
- Buttons: Bold (700)

## Message Styling

### User Message
```
┌─────────────────────────────────┐
│ > What is machine learning?     │  ← Bright green border & text
│                                 │  ← Black background
└─────────────────────────────────┘
USER                                ← Label below, muted green
```

- Border: 2px solid green (#00FF00)
- Background: Black (#000000)
- Text: Bright green (#00FF00)
- Border radius: None (sharp corners, Matrix-style)
- Label: "USER" in muted green

### Assistant Message
```
$ ┌─────────────────────────────────┐
  │ Machine learning is a subset of │  ← Medium green border & text
  │ artificial intelligence that...  │  ← Black background
  └─────────────────────────────────┘
  LLAMA                               ← Label below, muted green
```

- Marker: `$` in green
- Border: 2px solid medium green (#00CC00)
- Background: Black (#000000)
- Text: Medium green (#00CC00)
- Border radius: None
- Label: "LLAMA" in muted green

## Input Field

### Default State
```
┌────────────────────────────────────────────────────┐
│ > ENTER YOUR QUERY...                        SEND  │  Muted border
│                                                    │
└────────────────────────────────────────────────────┘
```

- Border: 2px solid muted green (#003300)
- Background: Very dark green (#001100)
- Text: Bright green (#00FF00)
- Placeholder: Muted green (#003300)
- Button: Muted/disabled

### Focused State
```
┌════════════════════════════════════════════════════┐
│ > Tell me about neural networks                    │  Bright border
│                                                    │  with glow
└════════════════════════════════════════════════════┘
```

- Border: 2px solid bright green (#00FF00)
- Glow: Green shadow (drop-shadow effect)
- Background: Very dark green (#001100)
- Text: Bright green (#00FF00)

### Send Button

**Disabled** (empty input):
```
[SEND]  ← Muted, faded text, no hover
```

**Enabled** (has text):
```
[SEND]  ← Bright green, glows on hover, clickable
```

- Font: Bold, uppercase, monospace
- Size: 12px (xs)
- Padding: 4px 12px
- Border: 2px solid green
- Hover: Green background with bright glow

## Animations & Effects

### Glitch Effect (Title)
The "MATRIX CHAT" title has occasional glitch animations:

```
MATRIX CHAT          ← Normal
MMТЯIХС НЗ7          ← Glitched (offset, color shift, distortion)
MATRIX CHAT          ← Back to normal
```

- Animation: Glitch-text with clip-path
- Frequency: Every 2 seconds
- Duration: Quick bursts
- Effect: Simulates digital corruption

### Message Fade-In
New messages gently fade in from the bottom:

```
Message appears ← Slightly below normal
              ↑ Fades in
              ↑ Slides up
Message positioned normally ← Settles
```

- Duration: 300ms
- Easing: ease-out
- Transform: translateY(10px) → translateY(0)
- Opacity: 0 → 1

### Loading Animation
When waiting for a response:

```
▮ ▮ ▮   ← Dots pulsing
▮ ▮ ▮
▮ ▮ ▮
```

- Animation: Pulse
- Stagger: 100ms delay between dots
- Color: Green

### Button Hover
When hovering over enabled send button:

```
[SEND]  ← Green border, green glow
↓
[SEND]  ← Green background, bright glow, text goes dark
```

- Background: Transitions to green (#00FF00)
- Text: Changes to black (#000000) for contrast
- Glow: Bright green shadow effect
- Duration: Instant (CSS transition)

## Responsive Design

### Desktop (1024px+)
```
Max message width: 512px (lg:max-w-lg)
Padding: 24px (px-6)
Font sizes: Base size
```

### Tablet (768px+)
```
Max message width: 448px (md:max-w-md)
Padding: 24px
Font sizes: Smaller
```

### Mobile (< 768px)
```
Max message width: 384px
Padding: 24px (px-6)
Font sizes: Small (text-sm)
Full width minus padding
```

## Layout Proportions

### Header
- Height: Auto (fits content)
- Border: Bottom 2px green
- Padding: 16px 24px
- Content: Title + Connection info

### Message Area
- Flex: 1 (takes remaining space)
- Padding: 24px
- Gap: 16px between messages
- Overflow: Auto-scroll
- Min-height: 400px (on desktop)

### Input Area
- Height: Auto (fits textarea)
- Border: Top 2px green
- Padding: 24px
- Gap: 8px between elements
- Helper text: 8px padding below

## Visual Hierarchy

### Most Important
1. Message content (bright green, readable)
2. Input field (prominent with glow when focused)

### Secondary
3. Labels (muted green, small)
4. Borders (muted green, 2px)

### Tertiary
5. Helper text (very muted)
6. Background (pure black, recedes)

## Spacing System

- **Gaps between messages**: 16px (gap-4)
- **Padding in messages**: 16px (px-4, py-2)
- **Padding in input**: 12px (p-3)
- **Padding in container**: 24px (px-6, py-6/pb-6)
- **Border width**: 2px (consistent)

## Contrast & Accessibility

| Text | Background | Ratio |
|------|-----------|-------|
| #00FF00 (green) | #000000 (black) | 5.0 : 1 ✓ |
| #00CC00 (med) | #000000 (black) | 3.6 : 1 ✓ |
| #003300 (muted) | #000000 (black) | 1.0 : 1 ✗ |
| #FF0000 (error) | #000000 (black) | 2.1 : 1 ⚠ |

Note: Muted green is for decorative borders, not body text. Error messages can be read alongside context.

## CSS Classes Reference

```css
/* Matrix-specific utilities in globals.css */
.glitch              /* Glitch effect on text */
.animate-fadeIn      /* Message fade-in animation */
.animation-delay-*   /* Stagger animations */
.matrix-border       /* Border with green color */
.matrix-input        /* Styled input field */
.matrix-button       /* Styled button */
```

## Interactive States

### Links/Buttons

```
Normal       → [SEND]      (green border, green text)
Hover        → [SEND]      (green bg, black text, glow)
Active/Click → [SEND]      (instant feedback)
Disabled     → [SEND]      (muted, faded, no hover)
Focus        → [SEND]      (ring: green)
```

### Input

```
Default      → Input field (muted border)
Focus        → Input field (bright border, glow)
Typing       → Textarea expands
Error        → Red border/text for errors
```

## Error Messages

```
┌────────────────────────────────────────────┐
│ ⚠ ERROR: Cannot connect to Ollama          │  Red border & text
│ Make sure the Python backend is running... │
└────────────────────────────────────────────┘
```

- Border: 2px solid red (#FF0000)
- Background: Black (#000000)
- Text: Red (#FF0000)
- Icon: ⚠ 
- Position: Above input area

## Visual Density

The design is **medium density**:
- Generous padding (not cramped)
- Clear spacing between elements
- Readable text (14px base)
- Monospace font (wider than proportional)
- Borders give breathing room

This balances Matrix aesthetic with usability.

---

That's the complete visual specification! Every color, size, and effect is designed to create an immersive Matrix experience while remaining functional and accessible.
