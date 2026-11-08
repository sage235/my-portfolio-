import zlib

CHAR_WIDTHS = {
    ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667, '\'': 222,
    '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
    '0': 556, '1': 556, '2': 556, '3': 556, '4': 556, '5': 556, '6': 556, '7': 556,
    '8': 556, '9': 556, ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556,
    '@': 1015, 'A': 667, 'B': 667, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778,
    'H': 722, 'I': 278, 'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722, 'O': 778,
    'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944,
    'X': 667, 'Y': 667, 'Z': 611, '[': 278, '\\': 278, ']': 278, '^': 469, '_': 556,
    '`': 222, 'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556, 'f': 278, 'g': 556,
    'h': 556, 'i': 222, 'j': 222, 'k': 500, 'l': 222, 'm': 833, 'n': 556, 'o': 556,
    'p': 556, 'q': 556, 'r': 333, 's': 500, 't': 278, 'u': 556, 'v': 500, 'w': 722,
    'x': 500, 'y': 500, 'z': 500, '{': 334, '|': 260, '}': 334, '~': 584,
    '—': 1000, '–': 556, '•': 350, '·': 278, '’': 222, '“': 500, '”': 500, 'é': 556,
    'è': 556, 'ê': 556, 'ë': 556, 'à': 556, 'â': 556, 'î': 222, 'ï': 222, 'ô': 556
}

def text_width(text, font, size):
    factor = 1.05 if 'Bold' in font else 1.0
    total = sum(CHAR_WIDTHS.get(ch, 556) for ch in text)
    return total * size / 1000.0 * factor

def sanitize_cp1252(text_str):
    replacements = {
        '↗': '->',
        '→': '->',
    }
    res = []
    for ch in text_str:
        if ch in replacements:
            res.append(replacements[ch])
        else:
            try:
                ch.encode('cp1252')
                res.append(ch)
            except UnicodeEncodeError:
                res.append(' ')
    return ''.join(res)

class ResumeBuilder:
    def __init__(self, width=612, height=792):
        self.width = width
        self.height = height
        self.stream = []
        self.annots = []

    def set_color_fill(self, r, g, b):
        self.stream.append(f"{r:.3f} {g:.3f} {b:.3f} rg")

    def set_color_stroke(self, r, g, b):
        self.stream.append(f"{r:.3f} {g:.3f} {b:.3f} RG")

    def line(self, x1, y1, x2, y2, width=0.75, color=(0.8, 0.8, 0.8)):
        self.set_color_stroke(*color)
        self.stream.append(f"{width:.2f} w")
        self.stream.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def rect(self, x, y, w, h, fill=None, stroke=None, stroke_width=0.5):
        if fill:
            self.set_color_fill(*fill)
        if stroke:
            self.set_color_stroke(*stroke)
            self.stream.append(f"{stroke_width:.2f} w")
        op = "B" if fill and stroke else ("f" if fill else "S")
        self.stream.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re {op}")

    def text(self, font, size, x, y, text_str, color=(0.1, 0.1, 0.1)):
        self.set_color_fill(*color)
        clean = sanitize_cp1252(text_str).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        self.stream.append("BT")
        self.stream.append(f"/{font} {size:.2f} Tf")
        self.stream.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
        self.stream.append(f"({clean}) Tj")
        self.stream.append("ET")

    def text_right(self, font, size, right_x, y, text_str, color=(0.1, 0.1, 0.1)):
        w = text_width(text_str, font, size)
        self.text(font, size, right_x - w, y, text_str, color)

    def add_link(self, x, y, w, h, url):
        self.annots.append({
            'rect': [x, y, x + w, y + h],
            'url': url
        })

    def build(self, output_path):
        content_str = "\n".join(self.stream)
        content_bytes = content_str.encode("cp1252")
        compressed = zlib.compress(content_bytes)

        annot_ids = []
        next_id = 8
        for _ in self.annots:
            annot_ids.append(next_id)
            next_id += 1

        objs = {}
        objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
        annots_str = " ".join(f"{aid} 0 R" for aid in annot_ids)
        annots_field = f"/Annots [{annots_str}]" if annot_ids else ""
        objs[3] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width} {self.height}] /Contents 4 0 R {annots_field} /Resources << /Font << /F1 5 0 R /F2 6 0 R /F3 7 0 R >> /ProcSet [/PDF /Text] >> >>".encode("latin1")
        objs[4] = f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("latin1") + compressed + b"\nendstream"
        objs[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        objs[6] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        objs[7] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"

        for aid, a in zip(annot_ids, self.annots):
            r = a['rect']
            u = a['url'].replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            objs[aid] = f"<< /Type /Annot /Subtype /Link /Rect [{r[0]:.2f} {r[1]:.2f} {r[2]:.2f} {r[3]:.2f}] /Border [0 0 0] /A << /S /URI /URI ({u}) >> >>".encode("latin1")

        out = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
        offsets = {}
        total_len = len(out[0])

        for oid in range(1, next_id):
            offsets[oid] = total_len
            chunk = f"{oid} 0 obj\n".encode("latin1") + objs[oid] + b"\nendobj\n"
            out.append(chunk)
            total_len += len(chunk)

        xref_pos = total_len
        out.append(f"xref\n0 {next_id}\n0000000000 65535 f \n".encode("latin1"))
        for oid in range(1, next_id):
            out.append(f"{offsets[oid]:010d} 00000 n \n".encode("latin1"))

        out.append(f"trailer\n<< /Size {next_id} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin1"))

        with open(output_path, "wb") as f:
            f.write(b"".join(out))
        print(f"Generated {output_path} successfully ({total_len} bytes, {len(self.annots)} clickable links).")

def generate():
    pdf = ResumeBuilder(width=612, height=792)
    left = 36.0
    right = 612.0 - 36.0
    width = right - left
    
    # Palette
    C_NAME = (0.07, 0.11, 0.18)      # Deep Midnight Navy
    C_TITLE = (0.10, 0.38, 0.70)     # Vibrant Tech Blue
    C_HEAD = (0.08, 0.28, 0.54)      # Section Header Blue
    C_TEXT = (0.15, 0.18, 0.22)      # Charcoal Ink
    C_MUTED = (0.42, 0.46, 0.52)     # Muted Slate
    C_LINE = (0.80, 0.84, 0.90)      # Subtle Border
    C_LINK = (0.08, 0.38, 0.72)      # Clickable Link Blue

    y = 752.0

    # ==================== HEADER ====================
    pdf.text("F1", 21.0, left, y, "ASDODJI LE SAGE", C_NAME)
    pdf.text_right("F1", 9.6, right, y + 2.0, "Kigali, Rwanda", C_MUTED)
    y -= 16.0
    
    pdf.text("F1", 10.2, left, y, "SOFTWARE ENGINEER  |  BACKEND & DISTRIBUTED SYSTEMS", C_TITLE)
    y -= 15.0

    # Contact items with clickable links
    contacts = [
        ("lesageasdodji@gmail.com", "mailto:lesageasdodji@gmail.com"),
        ("+250 735 562 281", "tel:+250735562281"),
        ("linkedin.com/in/le-sage-asdodji", "https://www.linkedin.com/in/le-sage-asdodji/"),
        ("github.com/sage235", "https://github.com/sage235")
    ]
    cx = left
    for i, (label, link) in enumerate(contacts):
        w = text_width(label, "F2", 8.8)
        pdf.text("F2", 8.8, cx, y, label, C_LINK if link else C_TEXT)
        if link:
            pdf.add_link(cx, y - 1, w, 10.5, link)
        cx += w
        if i < len(contacts) - 1:
            sep = "   |   "
            sw = text_width(sep, "F2", 8.8)
            pdf.text("F2", 8.8, cx, y, sep, C_MUTED)
            cx += sw

    y -= 9.0
    pdf.line(left, y, right, y, width=1.2, color=C_HEAD)
    y -= 14.0

    # Professional Summary
    summary_l1 = "Software Engineering student at AUCA (graduating 2027) focused on building dependable, scalable, and secure backend systems."
    summary_l2 = "Demonstrated expertise in Java (Spring Boot), Python, and relational database modeling (PostgreSQL/MySQL), with certified"
    summary_l3 = "foundations in operating system internals, computer hardware architecture, network security, and professional freelancing."
    pdf.text("F2", 8.6, left, y, summary_l1, C_TEXT)
    y -= 11.5
    pdf.text("F2", 8.6, left, y, summary_l2, C_TEXT)
    y -= 11.5
    pdf.text("F2", 8.6, left, y, summary_l3, C_TEXT)
    y -= 16.0

    def draw_section_header(title):
        nonlocal y
        pdf.text("F1", 10.2, left, y, title.upper(), C_HEAD)
        tw = text_width(title.upper(), "F1", 10.2)
        pdf.line(left + tw + 8, y + 3, right, y + 3, width=0.6, color=C_LINE)
        y -= 14.0

    # ==================== CERTIFICATIONS & CREDENTIALS ====================
    draw_section_header("Certifications & Accreditations")

    certs = [
        {
            "name": "Python Essentials 1",
            "issuer": "Cisco Networking Academy & Python Institute",
            "date": "08 Nov 2026",
            "id": "9bfea074-9cf2-4a57-b46a-e23db70fc03c",
            "desc": "Fundamental computer programming in Python: control flow, loops, data collections (lists, tuples, dicts), functions, and algorithmic design (aligned with PCEP certification).",
            "url": "https://www.netacad.com/certificates/9bfea074-9cf2-4a57-b46a-e23db70fc03c"
        },
        {
            "name": "Freelancer Academy — Certificate of Achievement",
            "issuer": "ALX Africa",
            "date": "26 Oct 2026",
            "id": "4a23d284-bb68-4e02-99e0-930d2aabd8dd",
            "desc": "Client communication, proposal pitching, contract negotiation, project delivery excellence, and international freelancing positioning.",
            "url": "https://ehub.alxafrica.com/ob3/verify-certificate/4a23d284-bb68-4e02-99e0-930d2aabd8dd"
        },
        {
            "name": "Operating Systems Basics",
            "issuer": "Cisco Networking Academy",
            "date": "24 Oct 2026",
            "id": "77e1a51f-aff9-4c07-a28a-99fd3c7af27b",
            "desc": "Operating system architecture, process lifecycle, memory management, file systems, Linux & Windows CLI administration, and security hardening principles.",
            "url": "https://www.netacad.com/certificates/77e1a51f-aff9-4c07-a28a-99fd3c7af27b"
        },
        {
            "name": "Computer Hardware Basics",
            "issuer": "Cisco Networking Academy",
            "date": "13 Jun 2024",
            "id": "0acd7e07-7041-43a1-9f91-4247eaf096b2",
            "desc": "Hardware architecture: motherboards, CPUs, RAM, storage, power delivery, peripheral connectivity, hardware diagnostics, and workplace safety standards.",
            "url": "https://www.netacad.com/certificates/0acd7e07-7041-43a1-9f91-4247eaf096b2"
        }
    ]

    for c in certs:
        # Title and Issuer
        pdf.text("F1", 9.0, left, y, c["name"], C_NAME)
        nw = text_width(c["name"], "F1", 9.0)
        pdf.text("F3", 8.4, left + nw + 6, y, f"·  {c['issuer']}", C_MUTED)
        pdf.text_right("F1", 8.4, right, y, c["date"], C_MUTED)
        y -= 11.2
        
        # Details & ID + Link
        desc_text = c["desc"]
        pdf.text("F2", 8.2, left + 8, y, f"•  {desc_text}", C_TEXT)
        y -= 10.5
        
        # ID line
        id_label = f"Credential ID: {c['id']}"
        pdf.text("F2", 7.6, left + 16, y, id_label, C_MUTED)
        iw = text_width(id_label, "F2", 7.6)
        verify_label = "[Verify Credential ->]"
        vw = text_width(verify_label, "F1", 7.6)
        pdf.text("F1", 7.6, left + 16 + iw + 6, y, verify_label, C_LINK)
        pdf.add_link(left + 16 + iw + 6, y - 1, vw, 9.5, c["url"])
        
        y -= 13.5

    y -= 3.0

    # ==================== TECHNICAL SKILLS ====================
    draw_section_header("Technical Skills")

    skills = [
        ("Backend & Languages:", "Java (Java 17/21, Spring Boot, Spring Security, JPA/Hibernate), Python (Scripting, Pandas), PHP, JavaScript, SQL"),
        ("Databases & Architecture:", "PostgreSQL, MySQL, MongoDB, Database Normalization, REST APIs, Microservices, Clean Architecture"),
        ("Systems, Security & QA:", "Linux CLI & Windows Administration, OS Hardening, Computer Hardware, VAPT Fundamentals, Unit Testing, QA"),
        ("Tools & Methodologies:", "Git, GitHub Actions, Maven, Postman, Agile/Scrum, Defensive Programming, Test Plans"),
        ("Spoken Languages:", "French (Native), English (Professional Working Proficiency)")
    ]

    for label, val in skills:
        pdf.text("F1", 8.7, left, y, label, C_NAME)
        lw = text_width(label, "F1", 8.7)
        pdf.text("F2", 8.4, left + lw + 6, y, val, C_TEXT)
        y -= 12.8

    y -= 3.0

    # ==================== FEATURED PROJECTS ====================
    draw_section_header("Featured Projects")

    projects = [
        {
            "name": "Pharma Finder",
            "tech": "Java, Spring Boot, PostgreSQL, REST APIs",
            "url": "https://github.com/sage235/pharmaback",
            "bullets": [
                "Engineered cross-border pharmaceutical platform enabling patients to search prescription medicines and discover certified nearby pharmacies.",
                "Built resilient PostgreSQL data schemas and RESTful order endpoints facilitating secure real-time inventory checks and delivery dispatching."
            ]
        },
        {
            "name": "LockSave — Secure Digital Wallet",
            "tech": "Java, Spring Boot, Spring Security, ACID Transactions",
            "url": "https://github.com/sage235/locksave",
            "bullets": [
                "Architected digital wallet engine across 600+ commits with double-entry accounting principles, atomic transactions, and balance guarantees.",
                "Implemented secure authentication, cryptographic safeguards, and granular role authorization mitigating financial concurrency risks."
            ]
        },
        {
            "name": "Restaurant Management Platform",
            "tech": "Java, Spring Boot, RESTful Web Services, SQL",
            "url": "https://github.com/sage235/restaurant-backend",
            "bullets": [
                "Engineered core server-side services powering restaurant operations: real-time menu management, dynamic order pipelines, and billing analytics."
            ]
        },
        {
            "name": "Rent House Management Platform",
            "tech": "Spring Boot, PostgreSQL, Hibernate, RBAC",
            "url": "https://github.com/sage235",
            "bullets": [
                "Delivered comprehensive rental property solution featuring hierarchical location trees, multi-tier RBAC, and automated lease contracts."
            ]
        },
        {
            "name": "Hotel Management & Booking System",
            "tech": "PHP, MySQL, Web UI",
            "url": "https://github.com/sage235",
            "bullets": [
                "Constructed full-cycle hospitality management platform with real-time room availability, secure guest authentication, and an analytics dashboard."
            ]
        },
        {
            "name": "Football Data Analytics & VAPT Security Lab",
            "tech": "Python, Pandas, Linux Hardening, Security Auditing",
            "url": "https://github.com/sage235",
            "bullets": [
                "Created automated data ETL and statistical visualization pipelines using Python/Pandas; performed network vulnerability assessments."
            ]
        }
    ]

    for p in projects:
        pdf.text("F1", 9.0, left, y, p["name"], C_NAME)
        pw = text_width(p["name"], "F1", 9.0)
        pdf.text("F3", 8.3, left + pw + 6, y, f"|  {p['tech']}", C_MUTED)
        
        gh_label = "[GitHub ->]"
        gw = text_width(gh_label, "F1", 8.0)
        pdf.text_right("F1", 8.0, right, y, gh_label, C_LINK)
        pdf.add_link(right - gw, y - 1, gw, 9.5, p["url"])
        
        y -= 11.0
        for b in p["bullets"]:
            pdf.text("F2", 8.2, left + 8, y, f"•  {b}", C_TEXT)
            y -= 10.2
        y -= 3.5

    y -= 2.0

    # ==================== EDUCATION ====================
    draw_section_header("Education")

    # AUCA
    pdf.text("F1", 9.0, left, y, "Bachelor of Software Engineering (BSc.)", C_NAME)
    pdf.text_right("F1", 8.5, right, y, "2023 – 2027 (In Progress)", C_MUTED)
    y -= 11.2
    pdf.text("F3", 8.4, left, y, "Adventist University of Central Africa (AUCA)  ·  Kigali, Rwanda", C_TITLE)
    y -= 10.5
    pdf.text("F2", 8.2, left + 8, y, "• Focus: Data Structures & Algorithms, Advanced Databases, Network Security, Software Testing & QA, Enterprise Systems Development.", C_TEXT)
    y -= 13.5

    # High School
    pdf.text("F1", 8.8, left, y, "Secondary School Diploma — Science Track", C_NAME)
    pdf.text_right("F1", 8.5, right, y, "Graduated 2023", C_MUTED)
    y -= 10.8
    pdf.text("F3", 8.4, left, y, "Complexe Scolaire Frère Polycarpe", C_TITLE)
    y -= 10.2
    pdf.text("F2", 8.2, left + 8, y, "• Rigorous academic curriculum in advanced mathematics, analytical reasoning, physics, and chemistry.", C_TEXT)

    # Footer Divider & Interactive Portfolio Note
    y -= 22.0
    pdf.line(left, y, right, y, width=0.6, color=C_LINE)
    y -= 12.0
    port_text = "Interactive Web Portfolio: https://sage235.github.io/my-portfolio-/"
    pw = text_width(port_text, "F1", 8.2)
    pdf.text("F1", 8.2, left, y, port_text, C_LINK)
    pdf.add_link(left, y - 1, pw, 9.5, "https://sage235.github.io/my-portfolio-/")
    
    pdf.text_right("F3", 7.8, right, y, "Verifiable credentials & code repositories available online", C_MUTED)

    print(f"Final vertical position Y = {y:.1f} (bottom margin threshold: 35.0)")

    output_file = "ASDODJI_Le_Sage_Resume.pdf"
    pdf.build(output_file)

if __name__ == "__main__":
    generate()
