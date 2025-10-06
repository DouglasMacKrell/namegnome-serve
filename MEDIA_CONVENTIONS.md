<!-- MEDIA_CONVENTIONS.md | NameGnome Serve | Full Media File Naming Conventions -->

# 📐 Media File Naming Conventions (Plex-Compatible)

Plex, Jellyfin, and similar media servers rely on **strict file and folder naming conventions** to correctly match media files to metadata from providers like TMDB, TVDB, and MusicBrainz. Deviations from these conventions often result in incorrect matches, missing artwork, or episodes appearing out of order.

Below are the **cleaned and clarified rules**, fully inlined here for Cursor.

---

## 1. Core Naming Principles

**Why this matters:** Plex parses file and directory names to determine media type, title, year, season/episode numbers, and track info. Consistent patterns are crucial for reliable matching.

- Use ASCII characters only; avoid special characters or diacritics when possible.
- Words are separated by spaces, dots (.), hyphens (-), or underscores (_). Consistency within a directory is preferred.
- Years must be enclosed in parentheses () immediately following the title:
  `Movie Title (1999).mkv`
- **Season and episode numbering use the `SxxEyy` format** (e.g. `S01E02`) for TV series.
- Multi‑episode TV files must list each episode number consecutively with no gaps:
  `Show Name - S01E01-E02 - <Episode Title 1> & <Episode Title 2>.mp4`
- Avoid clutter like release group tags, resolution, codecs, or extra brackets in filenames unless they are clearly separated at the end.

Examples:
```

Paw Patrol (2013)
Paw Patrol - S07E04 - Mighty Pups Charged Up Pups Vs Three Super Baddies.mp4
The Matrix (1999).mkv

```

---

## 2. Movies

**Why this matters:** Plex matches movies using `Title (Year)` as the canonical lookup key. Extra tags or incorrect formatting can break matching.

**Rules:**
- File name format:
  `Movie Title (Year).ext`
- Directory format:
  `Movie Title (Year)/Movie Title (Year).ext`
- For multi‑part films (e.g., disc splits), use `- Part 1`, `- Part 2` suffixes:
  `The Lord of the Rings The Fellowship of the Ring (2001) - Part 1.mkv`
- Year is mandatory for ambiguous titles (e.g., remakes):
  `Danger Mouse (1981).mp4` vs `Danger Mouse (2015).mp4`
- Optional metadata like resolution or source can be appended **after** the core naming, separated by hyphens:
  `The Matrix (1999) - 1080p.mkv`

Examples:
```

The Matrix (1999)/The Matrix (1999).mkv
Danger Mouse (2015)/Danger Mouse (2015).mp4
The Lord of the Rings The Fellowship of the Ring (2001)/The Lord of the Rings The Fellowship of the Ring (2001) - Part 1.mkv

```

---

## 3. TV Series

**Why this matters:** TV metadata lookups depend heavily on season and episode numbering. Anthology and multi‑episode files introduce complexity that requires precise adherence to numbering and title rules.

**Rules:**
- Directory structure:
```

Show Name (Year)/Season 07/Show Name - S07E04 - Episode Title.mp4

```
- **Single episode files:**
  `Paw Patrol - S03E10 - Pups Save Friendship Day.mp4`
- **Multi‑episode files:** list episodes consecutively with hyphenated episode numbers, and both episode titles separated by an "&":
  `Paw Patrol - S03E03-E04 - Pups Save a Goldrush & Pups Save the Paw Patroller.mp4`
- If multiple episodes are contained but **titles are incomplete or truncated**, the **titles take precedence** over numbering. The LLM should use fuzzy title matching and episode adjacency from the API to correct numbering.
- **Anthology files** may contain multiple segments; sometimes **subtitles appear only once** in the filename. For example input:
```

Paw Patrol-S07E04-Mighty Pups Charged Up Pups Vs Three Super Baddies.mp4

```
  The subtitle “Mighty Pups” may apply to multiple segments inside the file. Episode numbering should be derived from title adjacency in the API, not the filename alone.

### Anthology Edge Cases
- First pass might produce overly broad episode groupings (e.g., `01-02, 03-04, 04-05`).
- Second pass (LLM + deterministic refinement) can catch and fix overlaps or single‑episode splits, yielding `01-02, 03, 04-05`.
- Input episode numbering in anthology mode is **never trusted**; titles and provider adjacency are the ground truth.
- Only accept and match input numbering to the API response if no title is included in the file name!


Examples:
```

Paw Patrol (2013)/Season 07/S07E04.mp4
Paw Patrol (2013)/Season 07/S07E01-E02.mp4

```

---

## 4. Music

**Why this matters:** Music metadata matching relies on artist, album, year, and track numbering. Deviations lead to tracks being misfiled or artwork missing.

**Rules:**
- Directory structure:
```

Artist/Album (Year)/Track## - Track Title.ext

```
- Track numbers must be zero‑padded to 2 digits.
- Avoid extra tags or live performance notes unless clearly separated at the end.
- Artist names should match MusicBrainz canonical forms for best matching.

Examples:
```

Daft Punk/Discovery (2001)/Track01 - One More Time.mp3
Daft Punk/Discovery (2001)/Track02 - Aerodynamic.mp3

```

---

## 5. Directory Naming

**Why this matters:** Plex uses folder names as additional context. Correct directory structures speed up matching and reduce ambiguity.

**Rules:**
- Movies: `Title (Year)/Title (Year).ext`
- TV: `Show Name (Year)/Season XX/Show Name - SxxEyy - Title.ext`
- Music: `Artist/Album (Year)/Track## - Track Title.ext`
- No trailing spaces, special characters, or inconsistent casing.

---

## 6. Anthology Edge Cases (Expanded)

**Why this matters:** Anthology series often break strict sequential numbering. Subtitles may be truncated, repeated once, or omitted. Titles must drive episode mapping.

**Rules:**
- Input episode numbers are unreliable; **titles + provider adjacency** are authoritative.
- The LLM may need to perform **multi‑pass planning**:
  - First pass: generate preliminary episode groups based on naive parsing.
  - Second pass: correct groupings using API adjacency and fuzzy title matching.

**Example:**
```

Input filename: Paw Patrol - S07E04 - Mighty Pups Charged Up Pups Vs Three Super Baddies.mp4
First pass match: 01-02, 03-04, 04-05
Second pass fix:  01-02, 03, 04-05

```

---

## 7. Quick Reference Table

| Media Type | Directory Example               | File Naming Example |
|-----------:|---------------------------------|---------------------|
| Movie      | The Matrix (1999)               | The Matrix (1999).mkv |
| TV        | Paw Patrol (2013)/Season 07     | Paw Patrol - S07E04 - Mighty Pups Charged Up Pups Vs Three Super Baddies.mp4 |
| Music      | Daft Punk/Discovery (2001)     | Track01 - One More Time.mp3 |
