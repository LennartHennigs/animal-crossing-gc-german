# Plan: build a German GAFE01 ISO

Pipeline (scripts in this folder; artifacts written alongside):

1. **Segment** `message_data.bin` into dialog chains.
   Walk each entry's control codes; terminator = first LAST / CONTINUE /
   SELECT_WINDOW / MSG_TIME_END code. CONTINUE chains into the next entry.
   Output: list of chains `[(first_entry, last_entry)]`.

2. **Map** US chains → PAL BMG ids.
   Strip codes from concatenated chain text and from EN BMG messages; banded
   fuzzy match (4-gram Dice score, monotonic constraint, band around the
   anchor-interpolated diagonal). Output: `chain_to_pal.json` with scores.

3. **Tag conversion table** PAL `0x80` tags → US `7F` codes.
   For high-confidence pairs, align code positions between the US chain bytes
   and the EN BMG bytes; count `(group, idx)` ↔ `7F id` co-occurrences; keep the
   dominant mapping per tag. Hand-check the frequent ones (player name, town
   name, pauses, color, voice). Output: `tag_map.json`.

4. **Rebuild the German bank.**
   For each mapped chain: take the DE BMG message (same id as EN), convert tags
   → US codes, then re-paginate across the chain's entries: split converted
   bytes at safe points (never inside a code), append each original entry's
   terminator sequence; last entry keeps the original dialog-ending codes.
   Unmapped chains keep original US bytes. Respect mMsg_MSG_BUF_MAX per entry.
   Output: new `message_data.bin` + `message_data_table.bin` (end-offset table).

5. **Repack + rebuild ISO.**
   Surgical RARC edit of `forest_2nd.arc`: append new file data, patch the FST
   entry's offset/size + header lengths. Then patch the US ISO: place the grown
   arc (relocated to end of image if needed), patch disc FST. Output:
   `Animal Crossing (USA) [German].iso`.

6. **Verify.** Round-trip decode of the rebuilt bank (samples across the file),
   structural checks (table monotonic, terminators intact, sizes within limits).
   Play-test on the Anbernic (user).

Later / stretch: smaller banks (mail, item names, select menus) via the same
map-and-convert approach; they're additional `*_data(_table).bin` pairs in
`forest_1st.arc` whose PAL text sits in the same BMG.

## Revision (after engine analysis)

Entry/chain semantics proved ambiguous (LAST codes and dialog heads occur
mid-entry; `cut` is always FALSE). Revised approach — **stream rewrite with
proportional table mapping**:

1. Split the whole 2.7 MB stream at LAST/TIME_END codes → true dialogs.
2. Map stream-dialogs → PAL ids (same fuzzy/LIS machinery, now on true units).
3. Replace mapped dialogs with tag-converted German bytes; keep unmapped
   dialogs byte-identical.
4. New table: an old entry boundary at fraction f inside dialog D lands at
   fraction f inside the German D (snapped off control codes); boundaries at
   dialog starts stay exact. Entry count/ids unchanged, so all hardcoded
   msg_no constants in game code stay valid.
5. Per-entry size must stay ≤ mMsg_MSG_BUF_MAX (1536).
