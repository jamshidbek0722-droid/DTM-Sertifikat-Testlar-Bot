class TextFormatter:
    # Admin Panel
    ADMIN_PANEL = "🛠 Boshqaruv paneli:"
    TEST_TITLE_PROMPT = "Test nomini kiriting (masalan: Matematika DTM #1):"
    TEST_SUBJECT_PROMPT = "Fan nomini kiriting (masalan: Matematika):"
    TEST_PDF_PROMPT = "Test savollari faylini (PDF) yuboring:"
    TEST_ANSWER_KEY_PROMPT = "Test javoblarini yuboring (masalan: 1a2b3c... yoki 1-a 2-b...):"
    TEST_SOLUTION_PDF_PROMPT = "Yechimlar faylini (PDF) yuboring (Yoki 'Otkazib yuborish' tugmasini bosing):"
    TEST_DURATION_PROMPT = "Test qancha vaqt davom etadi? (Minutlarda, masalan: 60):"
    TEST_SCHEDULE_PROMPT = "Test qachon boshlanadi? (YYYY-MM-DD HH:MM formatida yoki darhol boshlash uchun 'Hozir' deb yozing):"
    TEST_CONFIRM_PROMPT = "Barcha ma'lumotlar to'g'rimi?\n\nNomi: {title}\nFan: {subject}\nSavollar soni: {total_q}\nDavomiyligi: {duration} daqiqa"
    TEST_UPLOADED = "✅ Test muvaffaqiyatli saqlandi!"
    CANCELLED = "❌ Amal bekor qilindi."
    INVALID_INPUT = "⚠️ Noto'g'ri ma'lumot kiritdingiz, qaytadan urinib ko'ring."
    
    # User Flow
    WELCOME = "Assalomu alaykum, {name}! DTM va Milliy Sertifikat testlari botiga xush kelibsiz."
    ACTIVE_TESTS = "Barcha faol testlar:"
    NO_ACTIVE_TESTS = "Hozirgi vaqtda faol testlar yo'q."
    TEST_JOIN_SUCCESS = "Siz testga qo'shildingiz! Vaqt ketdi.\nJavoblarni 1a2b3c yoki 1-a 2-b formatida yuboring."
    TEST_ALREADY_SUBMITTED = "Siz bu testga javob yuborgansiz!"
    TEST_TIMEOUT = "Test vaqti tugagan, javobingiz qabul qilinmadi."
    SUBMIT_SUCCESS = "✅ Javobingiz qabul qilindi!\n\nNatija: {score}/{total} ({percentage}%)\n"
    PARSE_ERROR = "⚠️ Javoblar formatida xato bor:\n"
    MISSING_ANSWERS = "- Topilmagan savollar: {missing}\n"
    DUPLICATE_ANSWERS = "- Ikki marta yuborilgan savollar: {duplicates}\n"
    INVALID_OPTIONS = "- Noto'g'ri harflar: {invalid_opts}\n"
    
    @staticmethod
    def format_leaderboard(title: str, total_participants: int, top_submissions: list, avg_score: float, max_score: int, total_questions: int, cta_link: str) -> str:
        text = f"🏆 {title} — Natijalar\n\n"
        text += f"📊 Jami ishtirokchilar: {total_participants}\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, sub in enumerate(top_submissions):
            medal = medals[i] if i < 3 else f"🔟 {i+1}." if i == 9 else f"{i+1}."
            time_str = sub.submitted_at.strftime("%H:%M")
            text += f"{medal} {sub.full_name} — {sub.score}/{total_questions} ({sub.percentage}%) ⚡ {time_str}\n"
            
        text += f"\n📈 O'rtacha ball: {avg_score:.1f}/{total_questions} ({(avg_score/total_questions*100):.1f}%)\n"
        text += f"🎯 Eng yuqori ball: {max_score}/{total_questions}\n\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n📚 Kurslarimizga qo'shiling → {cta_link}"
        return text

fmt = TextFormatter()
