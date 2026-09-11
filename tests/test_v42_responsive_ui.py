
from pathlib import Path

def main():
    p=Path(__file__).parents[1]/"gui"/"main_window.py"
    s=p.read_text(encoding="utf-8")
    required=[
        "class FlowLayout(QLayout)",
        "def resizeEvent(self, event):",
        "def apply_responsive_layout(self):",
        "self.setMinimumSize(900, 600)",
        "w < 1180",
        "w < 980",
        "self.workspace.setSizes([left,center,right])",
        "self.center_splitter.setSizes([top,bottom])",
        "QHeaderView.Stretch",
    ]
    for token in required:
        assert token in s, token
    print("V4.2 responsive UI source regression: PASS")

if __name__=="__main__":
    main()
