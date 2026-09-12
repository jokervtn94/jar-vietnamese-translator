
import math
import re
from typing import List, Tuple
from models.data import ExtractedString
from core.encoding_utils import script_count

# High-confidence player-facing labels. Exact matches get a strong boost, including
# short labels that generic heuristics would otherwise discard.
UI_WORDS = {
    "ok","yes","no","on","off","go","hp","mp","xp","lv",
    "start","play","continue","load","save","options","settings","exit","quit",
    "back","next","help","sound","music","language","score","level","pause",
    "resume","select","menu","loading","cancel","retry","buy","sell","shop",
    "inventory","items","item","equip","attack","defend","skill","skills",
    "mission","missions","quest","quests","map","new game","game over",
    "press start","high score","new record","try again","main menu",
}

# Common words that often occur in real prose/UI. These are boosts only, never
# mandatory, so non-English strings are still accepted by structural heuristics.
HUMAN_WORD_HINTS = {
    "the","a","an","to","of","for","from","with","and","or","is","are","you",
    "your","this","that","please","press","choose","select","enter","cannot",
    "failed","complete","completed","locked","unlocked","bonus","time","life",
    "lives","points","stage","world","enemy","player","game",
}



TECHNICAL_SINGLE_WORDS = {
    "run","init","initialize","destroy","destroyapp","startapp","pauseapp",
    "paint","repaint","draw","drawstring","update","tick","loop","render",
    "loadimage","loadresource","get","set","add","remove","insert","delete",
    "read","write","flush","close","connect","disconnect","send","receive",
    "encode","decode","parse","serialize","deserialize","execute","invoke",
    "keypressed","keyreleased","pointerpressed","pointerreleased",
    "commandaction","sizechanged","notifydestroyed","platformrequest",
    "main","null","true","false","undefined","exception","errorcode",
}

NAME_HINTS = (
    "lang","language","locale","localization","l10n","i18n","text","texts",
    "string","strings","message","messages","menu","dialog","english","en_",
    "/en/","caption","label","labels","subtitle",
)

NEGATIVE_SOURCE_HINTS = (
    "/lib/","/libs/","/engine/","/crypto/","/codec/","/network/","/http/",
    "/util/","/utils/","/debug/","/test/","/tests/",
)

FILE_EXT_RE = re.compile(
    r'(?i)\.(?:class|java|jar|zip|png|jpg|jpeg|gif|bmp|mid|midi|mp3|wav|amr|'
    r'dat|bin|res|xml|json|properties|txt|cfg|ini|rms|db|pak|so|dll|exe)$'
)
URL_RE = re.compile(r'(?i)^(?:https?|ftp|file|jar):[/\\]')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
JAVA_DESCRIPTOR_RE = re.compile(
    r'^(?:\[*[BCDFIJSZV]|\[*L[A-Za-z0-9_/$]+;|'
    r'\([^)]*\)[BCDFIJSZV]|\([^)]*\)L[A-Za-z0-9_/$]+;)$'
)
PACKAGE_RE = re.compile(r'^(?:[a-zA-Z_$][\w$]*\.){2,}[A-Za-z_$][\w$]*$')
SLASH_PATH_RE = re.compile(r'^(?:[A-Za-z0-9_.-]+[/\\]){1,}[A-Za-z0-9_.-]+$')
HEX_RE = re.compile(r'^(?:0x)?[0-9a-fA-F]{8,}$')
UUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
IDENT_RE = re.compile(r'^[A-Za-z_$][A-Za-z0-9_$]*$')
SNAKE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+$')
CONST_RE = re.compile(r'^[A-Z][A-Z0-9_]{4,}$')
MIME_RE = re.compile(r'^[a-z]+/[a-z0-9.+-]+$', re.I)
XMLISH_RE = re.compile(r'^</?[A-Za-z][^>]*>$')
GAME_NUMERIC_LABEL_RE = re.compile(
    r'(?i)^(?:level|stage|round|wave|world|mission|quest|score|time|life|lives|hp|mp|xp)\s*[:#-]?\s*\d+$'
)
PRINTF_ONLY_RE = re.compile(r'^(?:%[-+#0-9.*$]*[a-zA-Z]\s*)+$')

# V4.10 precision helpers. These are deliberately narrow: they target script/
# identifier shapes that repeatedly appear in J2ME engines while preserving
# ordinary one-word UI labels and all CJK language text.
SCRIPT_COMMAND_WORDS = {
    "action","backward","control","delay","fadein","fadeout","film","flash",
    "halt","imagemap","mark","mask","movie","nfopen","nofight","paycall",
    "pcenter","poem","psound","push","random","reset","saction","sanimation",
    "scenter","spro","sserial","ssound","state","still","text","trigger",
    "setx","sety","xmove","xmoveto","ymove","ymoveto","verify","result",
    "record1","record2","record3","minl","ml","al","part","pay",
}

PREFIXED_ENGINE_TOKEN_RE = re.compile(
    r'^[acdfjmps](?:mission|player|save|speed|action|serial|sound|sprite|center|pro)$',
    re.I,
)
BRACKET_COMMAND_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*\[$')
COMMAND_SCRIPT_RE = re.compile(
    r'(?i)(?:^|[;\s])(?:aplayer|splayer|magic|item|equip|stage|scene|trigger|event|money|pay)\s+[^;]+;'
)
ODD_ASCII_BINARY_RE = re.compile(r'^[\x20-\x7e]+$')
PATH_FRAGMENT_RE = re.compile(r'^(?:[/\\][A-Za-z0-9_.-]+)+[/\\]?$')
MIDLET_META_RE = re.compile(r'(?i)^MIDlet-[A-Za-z0-9-]+$')
UPPER_CAMEL_TOKEN_RE = re.compile(r'^[A-Z][A-Za-z0-9]{4,}$')

class LanguageDetector:
    """
    V4.4 precision-first game-text classifier.

    Deep Scan remains high-recall. This class is the precision gate deciding
    what is likely to be player-facing language before it reaches the editor.
    """

    def __init__(self):
        self.last_filter_stats={"accepted":0,"rejected":0}

    @staticmethod
    def _entropy(s: str) -> float:
        if not s:
            return 0.0
        counts={}
        for ch in s:
            counts[ch]=counts.get(ch,0)+1
        n=len(s)
        return -sum((c/n)*math.log2(c/n) for c in counts.values())

    @staticmethod
    def _word_tokens(s: str):
        return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", s, flags=re.UNICODE)

    @staticmethod
    def _camel_case_identifier(s: str) -> bool:
        # Reject likely method/field names such as getPlayerName / drawString,
        # but not normal title case such as "NewGame" unless very code-like.
        return bool(
            len(s) >= 6
            and " " not in s
            and re.match(r'^[a-z][A-Za-z0-9]*$', s)
            and re.search(r'[A-Z]', s[1:])
        )

    def classify(self, value: str, source: str="", kind: str="") -> Tuple[int, List[str]]:
        raw=value
        s=" ".join(raw.split()).strip()
        reasons=[]
        if not s or len(s)>800:
            return -100,["empty/too long"]

        lower=s.lower()
        source_lower=source.lower()
        words=self._word_tokens(s)
        letters=sum(ch.isalpha() for ch in s)
        digits=sum(ch.isdigit() for ch in s)
        spaces=sum(ch.isspace() for ch in s)
        punct=sum((not ch.isalnum()) and (not ch.isspace()) for ch in s)
        length=len(s)
        cjk_chars=script_count(s)
        cjk_ratio=cjk_chars/max(1,length)

        if letters==0:
            return -100,["no letters"]

        score=0

        # ---------- hard/strong technical negatives ----------
        if "\x00" in raw:
            score-=35; reasons.append("embedded NUL")
        if URL_RE.search(s):
            score-=80; reasons.append("URL/protocol")
        if EMAIL_RE.fullmatch(s):
            score-=70; reasons.append("email")
        if JAVA_DESCRIPTOR_RE.fullmatch(s):
            score-=100; reasons.append("Java descriptor")
        if UUID_RE.fullmatch(s) or HEX_RE.fullmatch(s):
            score-=80; reasons.append("hash/id")
        if XMLISH_RE.fullmatch(s):
            score-=70; reasons.append("XML/markup element")
        if MIME_RE.fullmatch(s):
            score-=65; reasons.append("MIME type")
        if PACKAGE_RE.fullmatch(s):
            score-=70; reasons.append("package/class name")
        if SLASH_PATH_RE.fullmatch(s):
            score-=65; reasons.append("path")
        if PATH_FRAGMENT_RE.fullmatch(s):
            score-=85; reasons.append("path fragment")
        if MIDLET_META_RE.fullmatch(s):
            score-=90; reasons.append("MIDlet metadata key")
        if FILE_EXT_RE.search(s) and " " not in s:
            score-=55; reasons.append("filename")
        # V4.11: reject bare extension/path fragments such as `.map` that are
        # technical resource tokens, not player-facing labels.
        if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", s):
            return -100, ["bare file extension token"]
        if PRINTF_ONLY_RE.fullmatch(s):
            score-=60; reasons.append("format token only")
        if CONST_RE.fullmatch(s) and lower not in UI_WORDS:
            score-=55; reasons.append("constant identifier")
        if SNAKE_RE.fullmatch(s) and lower not in UI_WORDS:
            score-=50; reasons.append("snake_case identifier")
        if self._camel_case_identifier(s) and lower not in UI_WORDS:
            score-=42; reasons.append("camelCase identifier")
        if kind.startswith("class-string") and PREFIXED_ENGINE_TOKEN_RE.fullmatch(s):
            score-=85; reasons.append("prefixed engine token")
        if kind.startswith("class-string") and BRACKET_COMMAND_RE.fullmatch(s):
            score-=70; reasons.append("script command token")
        if kind.startswith("class-string") and lower in SCRIPT_COMMAND_WORDS and lower not in UI_WORDS:
            score-=58; reasons.append("engine/script command")

        # Binary command streams can accidentally satisfy a length prefix and be
        # mislabeled as safe text.  Detect command-list syntax before positive
        # language boosts are applied.
        if kind.startswith("binary:") and COMMAND_SCRIPT_RE.search(s):
            score-=100; reasons.append("binary command script")

        # ASCII-only binary runs need natural-language evidence. Random config
        # tables frequently contain long printable sequences such as nLv/vXi/ian
        # that are structurally framed but are not player-facing language.
        if kind.startswith("binary:") and cjk_chars == 0:
            if "\x7f" in s:
                score-=120; reasons.append("binary control byte in ASCII payload")
            if ODD_ASCII_BINARY_RE.fullmatch(s):
                odd_punct=sum(ch in "\\[]{}<>`|^~" for ch in s)
                repeated_engine_chunks=sum(lower.count(x) for x in ("nlv","vxi","ian"))
                if spaces == 0 and (
                    (length >= 5 and odd_punct >= 1)
                    or (length >= 5 and repeated_engine_chunks >= 2)
                ):
                    score-=95; reasons.append("random-looking ASCII binary payload")

        # Resource/class internals frequently found by Deep Scan.
        if any(x in lower for x in (
            "java/lang/","javax/microedition/","javax.microedition.",
            "com/nokia/","com.siemens.","bluetooth.","socket://","http://","https://",
        )):
            score-=90; reasons.append("platform/internal reference")

        # Plain lowercase class constants are frequently VM/script identifiers.
        # Keep known UI labels, but require stronger evidence for arbitrary tokens.
        if kind.startswith("class-string") and cjk_chars == 0 and IDENT_RE.fullmatch(s) and s.islower():
            if lower not in UI_WORDS and lower not in HUMAN_WORD_HINTS:
                score-=45; reasons.append("lowercase class identifier")
        if kind.startswith("class-string") and cjk_chars == 0 and UPPER_CAMEL_TOKEN_RE.fullmatch(s):
            if lower not in UI_WORDS:
                score-=55; reasons.append("class/type identifier")

        # ---------- strong positives ----------
        # V4.6 was calibrated mainly for English. CJK strings discovered in binary
        # resources were often extracted correctly and then rejected by this gate.
        # Script evidence is a strong language signal even without spaces/Latin words.
        if cjk_chars >= 2:
            score += 34
            reasons.append("CJK language text")
            if cjk_ratio >= 0.45:
                score += 12
            if 2 <= length <= 12:
                score += 8

        normalized=lower.strip(" .,!?:;…-'\"")
        if normalized in UI_WORDS:
            score+=90; reasons.append("known game UI label")
        elif GAME_NUMERIC_LABEL_RE.fullmatch(s):
            score+=60; reasons.append("game UI numeric label")
        elif normalized in TECHNICAL_SINGLE_WORDS and len(words) == 1:
            score-=48; reasons.append("common code/method token")

        if any(h in source_lower for h in NAME_HINTS):
            score+=22; reasons.append("language-like source path")
        if any(h in source_lower for h in NEGATIVE_SOURCE_HINTS):
            score-=12; reasons.append("technical source path")

        # Multi-word phrases are much more likely to be actual player text.
        if len(words)>=2:
            score+=24; reasons.append("multi-word phrase")
        if len(words)>=4:
            score+=12; reasons.append("sentence-like phrase")

        human_hint_hits=sum(1 for w in words if w.lower() in HUMAN_WORD_HINTS)
        if human_hint_hits:
            score+=min(24,human_hint_hits*6)
            reasons.append("natural-language word hits")

        # Spaces and sentence punctuation are useful presentation-text signals.
        if spaces>0:
            score+=8
        if s.endswith((".","!","?","…")):
            score+=9; reasons.append("sentence punctuation")

        # A one-word label can be valid if it looks like a normal display word.
        if len(words)==1 and 2<=length<=20:
            w=words[0]
            if w==s and not ("_" in s or "/" in s or "\\" in s):
                if s.islower() or s.istitle() or s.isupper():
                    score+=14; reasons.append("display-word shape")

        # Very short UI tokens require care. Whitelist-like shape accepted;
        # arbitrary short method/field fragments no longer pass automatically.
        if 1<=length<=4:
            if normalized in UI_WORDS:
                score+=20
            elif s.isalpha() and (s.isupper() or s.istitle()):
                score+=6
            else:
                score-=12

        # Ratios: human text usually has a high alphabetic ratio but not excessive
        # code punctuation/digits.
        alpha_ratio=letters/max(1,length)
        if alpha_ratio>=0.65:
            score+=10
        elif alpha_ratio<0.30:
            score-=28; reasons.append("low alphabetic ratio")

        if digits/max(1,length)>0.45:
            score-=25; reasons.append("digit-heavy")
        if punct/max(1,length)>0.30 and spaces==0:
            score-=22; reasons.append("punctuation-heavy")

        # Random-looking tokens/high entropy without spaces are often IDs/packed data.
        ent=self._entropy(s)
        if length>=12 and spaces==0 and ent>=4.0 and len(words)<=1:
            score-=22; reasons.append("high-entropy token")

        # Kind-aware calibration.
        if kind.startswith("class-string"):
            score+=5  # actual CONSTANT_String already has semantic signal
        elif kind.startswith("deep-"):
            score-=8  # deep discovery needs stronger evidence
        elif kind.startswith("binary:") and kind.endswith(":safe"):
            score+=4

        return score,reasons

    def _threshold(self, item: ExtractedString) -> int:
        # Deep raw discovery is noisy, so it needs stronger confidence.
        if item.kind.startswith("deep-binary"):
            return 28
        if item.kind.startswith("deep-text"):
            return 18
        if item.kind.startswith("class-string"):
            return 12
        if item.kind.startswith("binary:"):
            return 14
        return 14

    def filter_strings(self, strings: List[ExtractedString]) -> List[ExtractedString]:
        out=[]
        seen=set()
        accepted=rejected=0
        for item in strings:
            normalized=" ".join(item.value.split())
            if not normalized or normalized in seen:
                continue
            score,_=self.classify(item.value,item.source,item.kind)
            if score >= self._threshold(item):
                seen.add(normalized)
                out.append(item)
                accepted+=1
            else:
                rejected+=1
        self.last_filter_stats={"accepted":accepted,"rejected":rejected}
        return out

    def score(self, source: str, strings: List[ExtractedString]) -> Tuple[int, List[str]]:
        if not strings:
            return 0,[]

        reasons=[]
        item_scores=[self.classify(s.value,s.source,s.kind)[0] for s in strings]
        n=len(strings)

        # Candidate score reflects QUALITY, not only string count.
        strong=sum(1 for x in item_scores if x>=40)
        medium=sum(1 for x in item_scores if 20<=x<40)
        avg=sum(item_scores)/n

        score=0
        if strong:
            score+=min(35,strong*5)
            reasons.append(f"{strong} high-confidence game-text strings")
        if medium:
            score+=min(15,medium*2)

        lower_source=source.lower()
        if any(h in lower_source for h in NAME_HINTS):
            score+=22; reasons.append("source path suggests language content")

        ui_hits=0
        for item in strings:
            normalized=item.value.lower().strip(" .,!?:;…-'\"")
            if normalized in UI_WORDS:
                ui_hits+=1
        if ui_hits:
            score+=min(30,ui_hits*6)
            reasons.append(f"{ui_hits} known game UI labels")

        multi=sum(len(self._word_tokens(s.value))>=2 for s in strings)
        if multi/n>=0.30:
            score+=12; reasons.append("many natural-language phrases")

        if avg>=35:
            score+=15; reasons.append("high average text confidence")
        elif avg>=22:
            score+=8

        # Avoid rewarding huge noisy resources merely because they contain many runs.
        if n>=5:
            score+=5
        if n>=20 and strong/max(1,n)>=0.30:
            score+=5

        return min(100,max(0,int(round(score)))),reasons
