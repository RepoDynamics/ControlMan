

class SGR:
    temp = "\033[{}m"
    reset = temp.format(0)
    text_style = {
        'normal': '0',
        'bold': '1',
        'faint': '2',
        'italic': '3',
        'underline': '4',
        'blink': '5',
        'blink_fast': '6',
        'reverse': '7',
        'conceal': '8',
        'strike': '9',
    }
    color = {
        'black': 30,
        'red': 31,
        'green': 32,
        'yellow': 33,
        'blue': 34,
        'magenta': 35,
        'cyan': 36,
        'white': 37,
        'b_black': 90,
        'b_red': 91,
        'b_green': 92,
        'b_yellow': 93,
        'b_blue': 94,
        'b_magenta': 95,
        'b_cyan': 96,
        'b_white': 97,
    }

    @staticmethod
    def style(
        text_styles: int | str | list[int | str] = None,
        text_color: int | str = None,
        background_color: int | str = None
    ):
        style_str = ""
        if text_styles:
            if isinstance(text_styles, (str, int)):
                text_styles = [text_styles]
            if not isinstance(text_styles, list):
                raise TypeError("styles must be a string, an integer, or a list of strings or integers")
            for text_style in text_styles:
                if isinstance(text_style, int):
                    if text_style not in range(10):
                        raise ValueError(f"Invalid style code: {text_style}")
                    text_style_code = str(text_style)
                elif isinstance(text_style, str):
                    if text_style not in SGR.text_style:
                        raise ValueError(f"Invalid style name: {text_style}")
                    text_style_code = SGR.text_style[text_style]
                else:
                    raise TypeError(f"Invalid style type: {type(text_style)}")
                style_str += f"{text_style_code};"
        if text_color:
            if isinstance(text_color, int):
                if text_color not in list(range(30, 38)) + list(range(90, 98)):
                    raise ValueError(f"Invalid color code: {text_color}")
            elif isinstance(text_color, str):
                if text_color not in SGR.color:
                    raise ValueError(f"Invalid color name: {text_color}")
            else:
                raise TypeError(f"Invalid color type: {type(text_color)}")
            style_str += f"{SGR.color[text_color]};"
        if background_color:
            if isinstance(background_color, int):
                if background_color not in list(range(40, 48)) + list(range(100, 108)):
                    raise ValueError(f"Invalid color code: {background_color}")
            elif isinstance(background_color, str):
                if background_color not in SGR.color:
                    raise ValueError(f"Invalid color name: {background_color}")
            else:
                raise TypeError(f"Invalid color type: {type(background_color)}")
            style_str += f"{SGR.color[background_color] + 10};"
        if not style_str:
            return SGR.reset
        return SGR.temp.format(style_str.removesuffix(";"))

    @staticmethod
    def format(text, style: str):
        if style == "error":
            s1 = SGR.style(text_styles="bold", text_color="b_white", background_color="red")
            s2 = SGR.style(text_styles="bold", background_color="red")
            return f"{s1}ERROR! {s2}{text}{SGR.reset}"
        if style == "warning":
            s1 = SGR.style(text_styles="bold", text_color="b_white", background_color="yellow")
            s2 = SGR.style(text_styles="bold", background_color="yellow")
            return f"{s1}WARNING! {s2}{text}{SGR.reset}"
        if style == "info":
            style = SGR.style(text_styles="bold", text_color="b_blue")
        elif style == "success":
            style = SGR.style(text_styles="bold", text_color="green")
        return f"{style}{text}{SGR.reset}"
