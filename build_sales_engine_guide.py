"""Build the Ana Lead Tracker Sales Engine PDF guide."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

OUTPUT = "Ana_Lead_Tracker_Sales_Engine_Guide.pdf"

BLUE = HexColor("#1a56db")
DARK = HexColor("#1f2937")
GRAY = HexColor("#6b7280")
LIGHT_BG = HexColor("#f3f4f6")
WHITE = HexColor("#ffffff")
ACCENT = HexColor("#2563eb")
GREEN = HexColor("#059669")
BORDER = HexColor("#d1d5db")

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    "CoverTitle", parent=styles["Title"],
    fontSize=32, leading=38, textColor=DARK,
    spaceAfter=8, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    "CoverSubtitle", parent=styles["Normal"],
    fontSize=14, leading=20, textColor=GRAY,
    spaceAfter=40, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontSize=22, leading=28, textColor=BLUE,
    spaceBefore=24, spaceAfter=12,
))
styles.add(ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontSize=16, leading=22, textColor=DARK,
    spaceBefore=18, spaceAfter=8,
))
styles.add(ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontSize=13, leading=18, textColor=ACCENT,
    spaceBefore=12, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontSize=10.5, leading=16, textColor=DARK,
    spaceAfter=8, alignment=TA_JUSTIFY,
))
styles.add(ParagraphStyle(
    "BodyBold", parent=styles["Normal"],
    fontSize=10.5, leading=16, textColor=DARK,
    spaceAfter=8, fontName="Helvetica-Bold",
))
styles.add(ParagraphStyle(
    "BulletItem", parent=styles["Normal"],
    fontSize=10.5, leading=16, textColor=DARK,
    spaceAfter=4, leftIndent=20, bulletIndent=8,
    bulletFontName="Helvetica", bulletFontSize=10,
))
styles.add(ParagraphStyle(
    "Callout", parent=styles["Normal"],
    fontSize=10, leading=15, textColor=HexColor("#1e40af"),
    spaceAfter=10, leftIndent=12, rightIndent=12,
    borderPadding=8, backColor=HexColor("#eff6ff"),
    borderColor=HexColor("#93c5fd"), borderWidth=1,
    borderRadius=4,
))
styles.add(ParagraphStyle(
    "FooterStyle", parent=styles["Normal"],
    fontSize=8, textColor=GRAY, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    "StepNum", parent=styles["Normal"],
    fontSize=11, leading=16, textColor=WHITE,
    fontName="Helvetica-Bold", alignment=TA_CENTER,
))


def hr():
    return HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=12, spaceBefore=6)


def spacer(pts=12):
    return Spacer(1, pts)


def bullet(text):
    return Paragraph(text, styles["BulletItem"], bulletText="•")


def callout(text):
    return Paragraph(text, styles["Callout"])


def make_table(headers, rows, col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 14),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    story = []

    # ── COVER ──
    story.append(spacer(120))
    story.append(Paragraph("Ana Lead Tracker", styles["CoverTitle"]))
    story.append(Paragraph("Sales Engine Guide", styles["CoverTitle"]))
    story.append(spacer(16))
    story.append(Paragraph(
        "A complete guide to the methodologies, features, and daily workflow<br/>"
        "for closing Ana Receptionist deals with Phoenix-area SMBs.",
        styles["CoverSubtitle"],
    ))
    story.append(spacer(20))
    story.append(Paragraph("Itxaz  |  Internal Use Only  |  2026", styles["CoverSubtitle"]))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──
    story.append(Paragraph("Table of Contents", styles["H1"]))
    story.append(spacer(8))
    toc_items = [
        ("1.", "What Is the Sales Engine?"),
        ("2.", "The Methodologies Behind It"),
        ("3.", "Daily Cockpit"),
        ("4.", "Live Call Interface"),
        ("5.", "Objection Bible"),
        ("6.", "The Daily Workflow"),
        ("7.", "Quick Reference"),
    ]
    for num, title in toc_items:
        story.append(Paragraph(
            f"<b>{num}</b>&nbsp;&nbsp;&nbsp;{title}",
            styles["Body"],
        ))
    story.append(PageBreak())

    # ── SECTION 1: WHAT IS THE SALES ENGINE? ──
    story.append(Paragraph("1. What Is the Sales Engine?", styles["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Sales Engine is the conversion half of the Ana Lead Tracker. While the Lead Tracker "
        "finds and scores prospects, the Sales Engine is where you actually pick up the phone and "
        "close them.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "It is built specifically for <b>high-ticket consultative sales</b> in the $20K-$50K range. "
        "You are not doing spray-and-pray cold calling. You are making 10-15 highly targeted calls "
        "per day to pre-researched, pre-scored businesses that have a real need for Ana Receptionist.",
        styles["Body"],
    ))
    story.append(Paragraph("The Sales Engine has three pages:", styles["Body"]))
    story.append(make_table(
        ["Page", "Purpose"],
        [
            ["Daily Cockpit", "Your mission control. Shows who to call today, in what order, with what script."],
            ["Live Call", "Your in-call companion. Openers, objection handlers, discovery questions, notes, and call close-out."],
            ["Objection Bible", "Your reference library. Every objection you will hear, with tested handlers in English and Spanish."],
        ],
        col_widths=[1.8 * inch, 4.7 * inch],
    ))
    story.append(spacer(12))
    story.append(callout(
        "<b>Key concept:</b> Both Josue and Santiago share the same database. "
        "When one person calls a prospect and updates the status, the other person sees it immediately. "
        "No double-calling, no lost information."
    ))
    story.append(PageBreak())

    # ── SECTION 2: METHODOLOGIES ──
    story.append(Paragraph("2. The Methodologies Behind It", styles["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Sales Engine is not a generic CRM. Every feature is built on specific, proven sales "
        "methodologies chosen for one reason: they work for high-ticket B2B consultative sales to "
        "SMB owners. Here are the four frameworks woven into the system.",
        styles["Body"],
    ))
    story.append(spacer(6))

    # Connor Murray
    story.append(Paragraph("Connor Murray's Oracle 3-Part Value Statement", styles["H2"]))
    story.append(Paragraph("<i>Used in: Personalized Openers (Daily Cockpit + Live Call)</i>", styles["Body"]))
    story.append(Paragraph(
        "Connor Murray is the founder of Oracle and one of the top cold-call trainers in B2B sales. "
        "His 3-Part Value Statement is the framework behind every AI-generated opener in the system. "
        "The structure:",
        styles["Body"],
    ))
    story.append(bullet(
        "<b>Part 1 - Opening (Assumptive Formality):</b> A warm, casual greeting with downward inflection. "
        "You introduce yourself by name and move fast. No permission-asking ('do you have a minute?'), "
        "no nervous filler. Example: 'Hey Maria, this is Josue from Itxaz - how are you?'"
    ))
    story.append(bullet(
        "<b>Part 2 - Value Statement (30-45 seconds):</b> Who you are, why specifically THEM (cite their "
        "industry and a specific pain point), the outcome/transformation (not features), a reference to "
        "Ricardo Diaz Insurance as proof, and what you want (a meeting next week)."
    ))
    story.append(bullet(
        "<b>Part 3 - Close (Assumptive Next Step):</b> A specific calendar ask. 'How's Wednesday at 10 "
        "or Thursday at 2?' Never ask IF they want to meet. Assume the meeting is happening."
    ))
    story.append(callout(
        "<b>Why this works for Ana deals:</b> SMB owners are busy. They get cold calls daily. "
        "The 3-Part framework respects their time (45 seconds max), leads with THEIR pain (not your product), "
        "and closes with a specific ask instead of a vague 'let me send you info.'"
    ))
    story.append(spacer(8))

    # Connor Murray ARC
    story.append(Paragraph("Connor Murray's Acknowledge-Reframe-Reclose (ARC)", styles["H2"]))
    story.append(Paragraph("<i>Used in: Objection Bible + Live Call Objections Tab</i>", styles["Body"]))
    story.append(Paragraph(
        "The same Connor Murray framework, applied to handling objections. When a prospect pushes back, "
        "you follow three steps:",
        styles["Body"],
    ))
    story.append(bullet(
        "<b>Acknowledge:</b> Validate their concern genuinely. Make them feel heard. "
        "'I hear that a lot, and it is a real concern.' Never argue or dismiss."
    ))
    story.append(bullet(
        "<b>Reframe:</b> Offer a new angle with proof, data, or a story. This is where you shift the "
        "conversation without being pushy. Use Ricardo Diaz Insurance as social proof when it fits naturally."
    ))
    story.append(bullet(
        "<b>Reclose:</b> Bring it back to a specific next step. 'Worth seeing how it works for them? "
        "I have Wednesday at 10 or Thursday at 2.'"
    ))
    story.append(spacer(8))

    # Teddy Frank
    story.append(Paragraph("Teddy Frank's Hyper-Relevant Discovery (UserGems)", styles["H2"]))
    story.append(Paragraph("<i>Used in: Live Call Discovery Tab</i>", styles["Body"]))
    story.append(Paragraph(
        "Teddy Frank, head of sales at UserGems, teaches that discovery questions should not be generic. "
        "Every question should tie directly to the prospect's actual pain. The system includes 8 discovery "
        "questions designed specifically for Ana Receptionist prospects:",
        styles["Body"],
    ))
    story.append(make_table(
        ["#", "Topic", "What You Learn"],
        [
            ["1", "Call volume", "How many inbound calls per day - validates the scoring"],
            ["2", "Current handling", "What happens when everyone is busy - reveals the gap Ana fills"],
            ["3", "Loss", "What happens to unanswered calls - quantifies the pain"],
            ["4", "Opportunity cost", "Dollar value of missed calls - builds the ROI case"],
            ["5", "Bilingual need", "Spanish-speaking customer base - Ana's competitive advantage"],
            ["6", "Decision maker", "Who else is involved - prevents 'I need to ask my partner'"],
            ["7", "Urgency", "Seasonal or staffing pressure - creates timeline"],
            ["8", "Timeline", "How fast they want to move - closes the loop"],
        ],
        col_widths=[0.4 * inch, 1.3 * inch, 4.8 * inch],
    ))
    story.append(spacer(4))
    story.append(callout(
        "<b>Teddy's rule:</b> Listen 2x more than you talk. These questions are designed to get the prospect "
        "talking about their pain, not for you to pitch. The pitch comes after they have told you their problem."
    ))
    story.append(spacer(8))

    # Jason Bay + Superhuman
    story.append(Paragraph("Jason Bay (Outbound Squad) + Superhuman Prospecting", styles["H2"]))
    story.append(Paragraph("<i>Used in: Call List Curation + Overall Sales Engine Design</i>", styles["Body"]))
    story.append(Paragraph(
        "Jason Bay's philosophy: fewer, better calls beat high-volume dialing. Superhuman Prospecting's "
        "Human-to-Human (H2H) approach adds that every interaction should feel like a conversation between "
        "two people, not a script being read at someone.",
        styles["Body"],
    ))
    story.append(Paragraph("These principles shaped the Sales Engine design:", styles["Body"]))
    story.append(bullet(
        "<b>10-15 calls per day, not 100.</b> The Daily Cockpit defaults to 10 calls because that is the "
        "elite range for high-ticket sales. Quality over volume."
    ))
    story.append(bullet(
        "<b>Every call is pre-researched.</b> You never dial a number without knowing why that business "
        "is a fit, what their score is, and what evidence supports the call."
    ))
    story.append(bullet(
        "<b>AI-personalized openers.</b> Claude reads each prospect's data and writes a unique opener "
        "in your voice, so you sound like a person who did their homework, not someone reading a template."
    ))
    story.append(bullet(
        "<b>Bilingual as a superpower.</b> Everything in the Sales Engine works in English and Spanish. "
        "In the Phoenix market, being able to switch to native Spanish is a competitive advantage most "
        "competitors cannot match."
    ))
    story.append(PageBreak())

    # ── SECTION 3: DAILY COCKPIT ──
    story.append(Paragraph("3. Daily Cockpit", styles["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Daily Cockpit is your starting point every morning. It answers one question: "
        "<b>who should I call right now, and what should I say?</b>",
        styles["Body"],
    ))
    story.append(spacer(6))

    story.append(Paragraph("How the Call List Is Built", styles["H2"]))
    story.append(Paragraph(
        "The system does not just sort leads by score. It builds a <b>smart mix</b> designed for "
        "maximum pipeline velocity:",
        styles["Body"],
    ))
    story.append(make_table(
        ["Portion", "Source", "Why"],
        [
            ["50%", "Fresh leads (Research Done / New)", "Highest-score prospects you have not called yet. These are your best new opportunities."],
            ["30%", "Follow-ups (Call 1 or Call 2 Made)", "Prospects who did not convert on the first call. Most deals close on the 2nd or 3rd touch. Do not let them go cold."],
            ["20%", "Demo confirmations (Demo Booked)", "Prospects with a demo scheduled. A quick confirmation call reduces no-shows."],
        ],
        col_widths=[0.8 * inch, 2.2 * inch, 3.5 * inch],
    ))
    story.append(spacer(8))

    story.append(Paragraph("Controls", styles["H2"]))
    story.append(bullet("<b>Who's calling?</b> Select your name (Josue or Santiago). This personalizes the AI-generated scripts with YOUR name."))
    story.append(bullet("<b>Language:</b> English or Spanish. Switches the script language and the Live Call interface language."))
    story.append(bullet("<b>List size:</b> 5, 10, 15, or 20. Default is 10, the elite benchmark for high-ticket sales."))
    story.append(spacer(6))

    story.append(Paragraph("Today's Stats", styles["H2"]))
    story.append(Paragraph(
        "Four real-time metrics tracked per caller per day:",
        styles["Body"],
    ))
    story.append(bullet("<b>Calls today:</b> How many calls you have made today."))
    story.append(bullet("<b>Connected:</b> How many times you reached a human (not voicemail, not no answer)."))
    story.append(bullet("<b>Demos booked:</b> The number that matters most."))
    story.append(bullet("<b>Connect rate:</b> Connected / Calls. Elite benchmark is 20-30%."))
    story.append(spacer(6))

    story.append(Paragraph("Using the Personalized Opener", styles["H2"]))
    story.append(Paragraph(
        "Each lead card has an expandable section labeled <b>'Personalized opener (Connor Murray 3-Part Framework)'</b>. "
        "Click <b>Generate Script</b> and Claude will write a custom 30-45 second opener based on that specific "
        "business's industry, city, score, and key evidence. The script uses YOUR name as the caller.",
        styles["Body"],
    ))
    story.append(callout(
        "<b>Tip:</b> Generate scripts for your top 3-5 calls before you start dialing. "
        "Read them out loud once to get comfortable. Do not read them verbatim on the call - "
        "use them as a guide for the flow and key points."
    ))
    story.append(spacer(6))

    story.append(Paragraph("Starting a Call", styles["H2"]))
    story.append(Paragraph(
        "Click the blue <b>Start Call</b> button on any lead card. This:",
        styles["Body"],
    ))
    story.append(bullet("Opens the <b>Live Call</b> interface for that prospect"))
    story.append(bullet("Starts a timer so you can track call duration"))
    story.append(bullet("Creates a record in the database so the call is logged"))
    story.append(bullet("Carries over any script you already generated"))
    story.append(PageBreak())

    # ── SECTION 4: LIVE CALL ──
    story.append(Paragraph("4. Live Call Interface", styles["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Live Call page is your in-call companion. It has five tabs, each serving a specific "
        "purpose during the conversation. Think of it as your co-pilot while you are on the phone.",
        styles["Body"],
    ))
    story.append(spacer(8))

    # Tab 1
    story.append(Paragraph("Tab 1: Opener", styles["H2"]))
    story.append(Paragraph(
        "Shows the personalized script you generated from the Cockpit. If you did not generate one, "
        "you can do it here with the Generate Script button. Use this as your guide for the first "
        "30-45 seconds of the call.",
        styles["Body"],
    ))
    story.append(spacer(6))

    # Tab 2
    story.append(Paragraph("Tab 2: Objections", styles["H2"]))
    story.append(Paragraph(
        "When the prospect pushes back, open this tab. Every objection from the Objection Bible is "
        "listed here with the full Acknowledge-Reframe-Reclose handler, localized to your selected language.",
        styles["Body"],
    ))
    story.append(Paragraph("For each objection, you have two buttons:", styles["Body"]))
    story.append(bullet(
        "<b>Handled it:</b> The prospect engaged positively after your reframe. This logs a success "
        "and improves the handler's success rate in the analytics."
    ))
    story.append(bullet(
        "<b>Didn't work:</b> The prospect did not budge. This is equally valuable data - over time "
        "you will see which handlers need to be rewritten."
    ))
    story.append(spacer(6))

    # Tab 3
    story.append(Paragraph("Tab 3: Discovery", styles["H2"]))
    story.append(Paragraph(
        "Eight pre-written discovery questions based on the Teddy Frank methodology. Available in "
        "English and Spanish. Use these after your opener lands and the prospect is engaged.",
        styles["Body"],
    ))
    story.append(callout(
        "<b>When to use Discovery vs. Close:</b> If the prospect says 'tell me more' or asks a question, "
        "switch to Discovery. If they seem ready, skip straight to a calendar ask. "
        "Discovery is for warming up interested-but-not-convinced prospects."
    ))
    story.append(spacer(6))

    # Tab 4
    story.append(Paragraph("Tab 4: Notes", styles["H2"]))
    story.append(Paragraph(
        "A simple text area for live note-taking during the call. Click Save to persist. "
        "These notes are attached to the call record and visible in the lead's history. "
        "Write what matters: names mentioned, objections raised, follow-up promises, tone of the conversation.",
        styles["Body"],
    ))
    story.append(spacer(6))

    # Tab 5
    story.append(Paragraph("Tab 5: Close Out", styles["H2"]))
    story.append(Paragraph(
        "When the call ends, use this tab to log the outcome. Every field matters for future analysis:",
        styles["Body"],
    ))
    story.append(make_table(
        ["Field", "What to Enter"],
        [
            ["Outcome", "What happened: Demo Booked, Callback Requested, Voicemail Left, Gatekeeper Only, No Answer, Not Interested, Wrong Number, or Do Not Contact."],
            ["Connected", "Did you reach a human? Check if yes."],
            ["Reached DM", "Did you speak to the decision maker? Critical for pipeline accuracy."],
            ["Conversation quality", "Rate 1-10. Be honest - this trains future lead scoring."],
            ["Estimated deal value", "Default $35K. Adjust based on the prospect's size and needs ($20K-$50K range)."],
            ["Next action", "What is the specific next step? e.g., 'Send demo recap email Friday'"],
            ["Next action date", "When should the next step happen?"],
        ],
        col_widths=[1.6 * inch, 4.9 * inch],
    ))
    story.append(spacer(8))

    story.append(Paragraph("Automatic Status Updates", styles["H2"]))
    story.append(Paragraph(
        "When you close out a call, the system automatically updates the lead's status based on the outcome:",
        styles["Body"],
    ))
    story.append(bullet("<b>Demo Booked</b> sets status to 'Interested - Demo Booked'"))
    story.append(bullet("<b>Voicemail Left</b> sets status to 'Voicemail Left'"))
    story.append(bullet("<b>Not Interested / Do Not Contact</b> sets the matching status"))
    story.append(bullet(
        "<b>Other outcomes</b> (Callback, Gatekeeper, No Answer) auto-advance the call counter: "
        "New becomes Call 1 Made, then Call 2 Made, then Call 3 Made"
    ))
    story.append(callout(
        "<b>Why this matters:</b> After Call 3 with no progress, the lead falls out of the active call list. "
        "This prevents you from endlessly calling unresponsive prospects and focuses your energy on better leads."
    ))
    story.append(PageBreak())

    # ── SECTION 5: OBJECTION BIBLE ──
    story.append(Paragraph("5. Objection Bible", styles["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "The Objection Bible is your reference library of every objection you will hear when selling "
        "Ana Receptionist, with tested handlers in English and Spanish.",
        styles["Body"],
    ))
    story.append(spacer(6))

    story.append(Paragraph("Pre-Loaded Objections", styles["H2"]))
    story.append(Paragraph(
        "The system comes with 10 objections based on real sales conversations with Phoenix SMBs. "
        "Each one has been crafted using the Acknowledge-Reframe-Reclose framework:",
        styles["Body"],
    ))
    story.append(make_table(
        ["Objection", "Category"],
        [
            ["'We already have a receptionist'", "Competition"],
            ["'That sounds expensive'", "Price"],
            ["'My customers won't trust talking to AI'", "Trust"],
            ["'We don't get that many calls'", "Fit"],
            ["'Just send me some info'", "Information"],
            ["'I need to ask my partner'", "Authority"],
            ["'How is this different from voicemail?'", "Fit"],
            ["'We tried something like this before'", "Trust"],
            ["'Not ready right now, call me in 6 months'", "Timing"],
            ["'What about complex or Spanish calls?'", "Fit"],
        ],
        col_widths=[4.0 * inch, 2.5 * inch],
    ))
    story.append(spacer(8))

    story.append(Paragraph("Analytics", styles["H2"]))
    story.append(Paragraph(
        "The Objection Bible tracks three metrics at the top of the page:",
        styles["Body"],
    ))
    story.append(bullet("<b>Objections in bible:</b> Total number of objections cataloged."))
    story.append(bullet("<b>Total encounters:</b> How many times objections have been encountered across all calls."))
    story.append(bullet(
        "<b>Handler success rate:</b> What percentage of the time the Acknowledge-Reframe-Reclose "
        "handler resulted in a positive outcome. This is the number to watch - if a handler drops below "
        "50%, it is time to rewrite it."
    ))
    story.append(spacer(6))

    story.append(Paragraph("Editing and Adding Objections", styles["H2"]))
    story.append(Paragraph(
        "Every objection has an Edit form where you can update the English and Spanish text for all four "
        "parts (objection, acknowledge, reframe, reclose). You can also add entirely new objections using "
        "the 'Add new objection' form at the bottom of the page.",
        styles["Body"],
    ))
    story.append(callout(
        "<b>Best practice:</b> After every call where you hear something new, add it to the Bible immediately. "
        "If a handler did not work, update the reframe with what you wish you had said. "
        "The Bible gets stronger with every call."
    ))
    story.append(PageBreak())

    # ── SECTION 6: DAILY WORKFLOW ──
    story.append(Paragraph("6. The Daily Workflow", styles["H1"]))
    story.append(hr())
    story.append(Paragraph(
        "Here is the recommended daily workflow for using the Sales Engine. This takes about "
        "2-3 hours and is designed for maximum impact with minimum wasted effort.",
        styles["Body"],
    ))
    story.append(spacer(8))

    steps = [
        ("Prep (10 minutes)",
         "Open the Daily Cockpit. Select your name and language. "
         "Review your top 10 call list. Generate scripts for your top 3-5 prospects. "
         "Read each script out loud once."),
        ("Call Block (60-90 minutes)",
         "Work through your list top to bottom. Click Start Call to enter the Live Call interface. "
         "Use the Opener tab for the first 30 seconds. If the prospect raises an objection, open the Objections tab. "
         "If they engage, switch to Discovery. Take notes in real time."),
        ("Close Out (2 minutes per call)",
         "After each call, immediately close it out in the Close Out tab. "
         "Be honest about conversation quality. Set a specific next action with a date. "
         "The system auto-updates the lead status for you."),
        ("Debrief (10 minutes)",
         "Check your Today's Stats: calls, connections, demos, connect rate. "
         "If an objection stumped you, update the Bible with a better handler. "
         "If a script worked particularly well, note what made it different."),
    ]
    for i, (title, desc) in enumerate(steps, 1):
        story.append(Paragraph(f"Step {i}: {title}", styles["H2"]))
        story.append(Paragraph(desc, styles["Body"]))
        story.append(spacer(4))

    story.append(spacer(8))
    story.append(callout(
        "<b>The golden rule:</b> 10 great calls beat 50 mediocre ones. Every call in your list has been "
        "AI-scored and ranked. Trust the system, prepare for each call, and focus on having real conversations."
    ))
    story.append(PageBreak())

    # ── SECTION 7: QUICK REFERENCE ──
    story.append(Paragraph("7. Quick Reference", styles["H1"]))
    story.append(hr())
    story.append(spacer(6))

    story.append(Paragraph("Lead Statuses", styles["H2"]))
    story.append(make_table(
        ["Status", "Meaning", "Shows in Call List?"],
        [
            ["New", "Just entered the system, not yet researched", "Yes (fresh)"],
            ["Research Done", "AI-scored, ready to call", "Yes (fresh)"],
            ["Call 1 Made", "First call attempted", "Yes (follow-up)"],
            ["Call 2 Made", "Second call attempted", "Yes (follow-up)"],
            ["Call 3 Made", "Third call attempted", "No"],
            ["Voicemail Left", "Left a voicemail", "No"],
            ["No Answer (3+ attempts)", "Could not reach after multiple tries", "No"],
            ["Interested - Demo Booked", "Demo is scheduled", "Yes (confirmation)"],
            ["Not Interested", "Declined (reason required)", "No"],
            ["Do Not Contact", "Explicit opt-out", "No"],
            ["Closed Won", "Deal closed!", "No"],
            ["Closed Lost", "Deal lost", "No"],
        ],
        col_widths=[2.0 * inch, 2.8 * inch, 1.7 * inch],
    ))
    story.append(spacer(12))

    story.append(Paragraph("Call Outcomes", styles["H2"]))
    story.append(make_table(
        ["Outcome", "Auto-Sets Status To"],
        [
            ["Demo Booked", "Interested - Demo Booked"],
            ["Callback Requested", "Auto-advances call counter (Call 1 > 2 > 3)"],
            ["Voicemail Left", "Voicemail Left"],
            ["Gatekeeper Only", "Auto-advances call counter"],
            ["No Answer", "Auto-advances call counter"],
            ["Not Interested", "Not Interested"],
            ["Wrong Number", "Auto-advances call counter"],
            ["Do Not Contact", "Do Not Contact"],
        ],
        col_widths=[2.5 * inch, 4.0 * inch],
    ))
    story.append(spacer(12))

    story.append(Paragraph("Scoring Criteria", styles["H2"]))
    story.append(make_table(
        ["Criterion", "What It Measures (1-10)"],
        [
            ["Call Volume", "How many inbound calls the business handles daily"],
            ["Missed Call Pain", "How much revenue they lose from missed or abandoned calls"],
            ["Bilingual Opportunity", "Whether they serve Spanish-speaking customers"],
            ["Tech Readiness", "Existing tech sophistication and willingness to adopt AI"],
            ["Ease of Closing", "Decision-maker accessibility, budget signals, buying readiness"],
            ["Urgency", "Time-sensitive pain: seasonal demand, growth, staff turnover"],
        ],
        col_widths=[1.8 * inch, 4.7 * inch],
    ))
    story.append(spacer(20))

    story.append(hr())
    story.append(Paragraph(
        "Ana Lead Tracker Sales Engine Guide  |  Itxaz  |  2026",
        styles["FooterStyle"],
    ))

    doc.build(story)
    print(f"PDF created: {OUTPUT}")


if __name__ == "__main__":
    build()
