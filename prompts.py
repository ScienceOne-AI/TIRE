"""Generation prompts aligned with the submitted paper's Appendix C.1.

Templates marked as translated in the appendix are supplied in Chinese here.
The unit-test example is retained in full; the appendix abbreviates it.
"""

import hashlib
import json
import random
import re

PROMPT_VERSION = "submitted-appendix-c1-20261016-json-safe-v2"

# G01_formula_physics
FORMULAS = r"""你是专业的物理学家，请根据问题以及对应的题解列出涉及到的所有通用物理公式，每个公式按以下格式输出：
{
"name": "定理名称",
"formula": "LaTeX公式",
"description": "定理描述",
"applicable_range": "适用范围"
}
用```json ```包裹完整的JSON数组，所有字段使用中文。
如果无法解决该问题，请仍返回至少一个相关公式。
        

问题: {problem_text}


题解: {problem_solutions}"""

# G04_formula_filter
FORMULA_FILTER = r"""```json
{formula_record}                 
```

请你根据以上 JSON 字段内容，严格判断其合理性：

- name：公式名称，需通用且贴切
- formula：必须为 latex 格式的等式，且内容科学合理、无语法错误
- description：大致描述公式含义
- applicable_range：大致指定公式适用范围

请综合判断上述四项是否都合理且相互对应。  
如果全部合理且对应，请只返回 True；如有任何一项不合理或不对应，请只返回 False。  
无需解释原因，只返回 True 或 False。                 
"""

# G05_program
CODE = r"""
   ## 身份
你是一个物理与物理化学专家，并且熟练使用python。

## 任务
- 根据给定的物理或物理化学公式信息，请你生成一段python函数，表示这个公式。这个函数的输入为公式右面所有的变量，输出为计算公式左面的变量。公式中的常量不要作为输入隐含在函数里

### 公式信息
{
    "name": "{name}",
    "formula": "{formula}",
    "description": "{description}",
    "applicable_range": "{applicable_range}"
}

## 要求
- 输出python代码，在代码块外不要输出任何解释。
- 代码中要包含函数的输入参数和返回值的类型注释。
- 代码中要包含函数的docstring，描述函数的功能和参数。
- 把生成的代码放到json文件中，json的key是python_code，value就是生成的代码
## 代码要求
- 如果需要导入python包，在函数内导入，例如：def gravitational_acceleration(a: float, G: float, M: float, r: float) -> float: import numpy as np
## 返回格式
- 返回一个标准JSON对象，包含以下字段:
{
    "python_code": ""
}
        """

# G07_tests_later
UNIT_TESTS = r"""
## 身份
你是一名严谨的物理专家，精通 Python 单元测试（unittest）。

## 目标
基于给定“公式信息”与其对应的 Python 函数源码，实现高质量单元测试代码，验证函数是否正确实现公式：函数的返回值应等价于公式左侧物理量；函数的参数列表应覆盖公式右侧的所有自变量（公式中的物理常量被视为内部常量，不作为形参传入）。

### 公式信息
{
    "name": {name},
    "formula": {formula},
    "description": {description},
    "applicable_range": {applicable_range}
}

### 待测试的 Python 函数源码
{python_code}

## 生成要求
1. 输出格式：只返回一个合法 JSON 对象，唯一键 "test_cases"，其值是纯 Python 测试代码字符串。不得出现其他任何文字、说明、标签、反引号或额外键。
   {
     "test_cases": "..."
   }
2. 代码内不要再次导入或引用自身文件名 / 函数名所在模块（禁止出现 import xxx 与 from xxx import 函数本体）；仅允许必要的标准库导入（通常为 unittest、math；若未用到不要导入）。
3. 直接调用函数名，视为已在同文件上方定义。
4. 物理取值合理：符合数量级，避免非物理或负质量、负绝对温度等。
5. 期望值计算原则（重点，严禁“想当然”硬编码）：
   - 所有期望值必须用公式结构实时计算，绝不直接写拍脑袋近似数字（禁止魔法数字）。
   - 若公式含指数/对数/幂/根：使用 math.exp / math.log / ** 等表达式重建理论值；不写已近似的十进制截断。
   - 半衰期场景：expected = N0 * 0.5**n 或 N0 * math.exp(-lambda_ * t)，不写 N0/1024 这类除法常数硬编码除非表达式本身自然得出（示例：两次半衰期可写 N0 * 0.5**2；优先这类形式）。
   - “近似不变”测试（如极小衰减常数）必须：先用公式算 expected，再断言 actual 与 expected；严禁再写一个与 expected 不同来源的手工估计数字（例如 19999.999）。
   - 禁止出现第二个仅为了“接近”而对初值进行的人为凑值断言；如需证明变化极小，可再添加 self.assertLess(abs(expected - N0)/N0, 1e-5)。
6. 不允许：在同一测试中对同一返回值进行“公式期望值正确断言”后，再对一个手写近似常量二次断言。
7. 浮点断言策略：
   - 首选 self.assertAlmostEqual(expected, actual, places=适当位数)；位数依据数量级（通常 6~10）。
   - 如多量级跨度可用：rel = abs(expected - actual)/max(1.0, abs(expected))，并断言 rel < 某合理阈值（需给出依据）。
8. 常量（如 G, c, k_B 等）若函数未内置且需要参与期望值计算，可在测试中以同样数值定义，并与公式结构一致计算期望值。
9. 不使用随机、I/O、网络、第三方库。
10. 若公式包含幂/根/指数/对数，测试中显式给出期望值的物理推导表达式，而不是硬编码魔法数字。
11. 类命名：Test + 函数名（首字母大写驼峰）。测试方法命名：test_描述。

## 质量与自检（内部执行，不写入输出）
- 检查是否存在硬编码与公式结构无直接对应的常量；若存在，改为符号表达式。
- 检查是否出现“重复断言 + 人为估值”模式；若有，移除人为估值。
- 检查所有 expected 定义都独立于被测函数（禁止用被测函数反推自身）。

## 严格输出规范
- 不输出任何多余文字（如：Here is、Below are、Explanation、<artifact>、```、I'll create a set of test cases for the Hubble's Law function. Here's a JSON object containing the test cases等等）。
- 不在 JSON 之外输出内容。
- JSON 中 test_cases 的字符串内部可以含换行与缩进。

### 测试单元示例（示例不要照搬，需按当前函数特性重写）
{
  "test_cases": "import unittest\n\nclass TestPhotonSphereRadius(unittest.TestCase):\n    def test_sun_mass_blackhole(self):\n        G = 6.67430e-11\n        c = 299792458.0\n        M = 1.989e30\n        expected_rc = 3 * G * M / (c ** 2)\n        actual_rc = photon_sphere_radius(G, M, c)\n        self.assertAlmostEqual(actual_rc, expected_rc, places=6)\n\nif __name__ == '__main__':\n    unittest.main()\n"
}

## 失败处理
若信息缺失无法构造测试，仍需返回合法 JSON，test_cases 内放置最小 unittest 结构并在 setUp 中用 self.fail('insufficient data') 标记，但优先尝试正常生成。
"""

# G08_parameters
PARAMETERS = r"""## 角色
你是一名精通物理化学与 Python 科学计算的专家。

## 任务
现提供某物理或物理化学公式的结构化信息及其对应的 Python 实现函数。请你基于函数签名与公式物理意义，构造一组“可通过且有物理合理性”的测试输入参数，并仅返回 JSON。  
函数返回值对应公式左侧物理量；函数的所有入参对应公式右侧（以及实现中隐含需要的）变量。代码中使用的常量不需要出现在测试输入里。


### Formula Information
{
    "name": "{name}",
    "formula": "{formula}", 
    "applicable_range": "{applicable_range}"
}

### Python Function
{function_code}

## 生成要求
1. 仅读取函数签名中所有入参，逐一为其生成合理物理量取值；不得遗漏任何参数；避免使用 0 或不合理极端值（除非物理或函数逻辑明确允许）。  
2. 若某参数应为数组 / 向量 / 矩阵（依据：
   - 函数体中出现诸如形状操作、切片、广播、逐元素运算；
   - 变量被传入 np.array / np.asarray / np.stack / np.concatenate / 数组数学运算；
   则生成时使用列表来表示， 否则不能作为json存储，元素取值物理合理且数量简洁（2~4 个为宜）。  
3. 若参数语义表示：
   - 温度：使用 250–1500 K 合理范围（依据公式适用域可微调）；
   - 压力：使用 1e3–1e7 Pa（或根据公式说明）；
   - 长度（m）避免 0 与负值；
   - 时间（s）使用正值；
   - 浓度 / 比例：在 (0,1] 合理区间；
   - 能量 / 焓 / 熵等：符号与典型数量级符合常见物理情景；
   - 频率 / 速率常数：正值；
   - 若名称含 ref / std / baseline，可用常见标准条件值；
   - 若名称含 n, count, steps，给出正整数或短数组。
4. 确保各参数之间不产生明显物理矛盾（例如：分压之和不超过总压；摩尔分数之和不明显大于 1）。  
5. 不臆造函数未声明的参数，不修改参数名。  
6. 不输出解释文字、注释或多余键，仅输出 JSON。  
7. JSON 结构：
{
    "input_para": {
        "<param1>": <value>,
        "<param2>": <value>
        ...
    }
}
其中 value 若为数组，直接写成列表形式字面量（无需引号）。字符串参数保留引号。布尔参数用 true/false，不要使用 Python 的 True/False。  
8. 避免使用随机数（不使用 np.random）。  
9. 若函数含 *args / **kwargs，忽略之（仅处理显式命名参数）。  
10. 若存在参数依赖关系（例如：某数组长度需匹配另一参数），需满足代码逻辑。  
11. 所有数值选择尽量保证计算后不会产生除零、log 负数、开方负数、溢出（exp 过大）等数值错误。  
12. 若公式适用范围（applicable_range）提供限定，需在该范围内选值；无法解析时，采取保守常规物理范围。

## 输出
仅输出最终 JSON，无前后缀、无 Markdown 代码块、无额外说明。

## 示例（示意，不代表真实函数）
{
    "input_para": {
        "T": 298.15,
        "P": 101325.0,
        "y": [0.21, 0.79],
        "k0": 1.2e5
    }
}
（正式输出中不要包含此示例。）"""

# G09_verbalization_later
QUESTIONS = r"""## Identity
You are an expert in both Physics and Physical Chemistry, with strong proficiency in quantitative problem design and solution explanation. You rigorously apply dimensional analysis, significant figures, and domain-appropriate terminology.

## Tasks
Task 1: Create a calculation problem based on the provided formula metadata and input parameters (the parameters will be injected separately as structured data; do NOT list or restate them explicitly).
Task 2: Provide a detailed, logically ordered solution that applies the given formula correctly, with proper unit handling and clear justification of each step.
Task 3: Ensure the final numerical result exactly matches the provided answer parameter.

## Scope
You may generate a problem in any of the following subjects:
- Classical mechanics
- Electromagnetism
- Optics
- Thermodynamics and statistical physics
- Quantum mechanics
- Atomic, nuclear, and particle physics
- General physics
- Physical chemistry
- Quantum chemistry
provided the selected scenario is realistic and consistent with the formula's applicable range.

## Formula Information
The following structured block defines the formula context:
{
    "name": "{name}",
    "formula": "{formula}",
    "applicable_range": "{applicable_range}"
}

## Reference Code (for reference)
{function_code}

## Parameter Context
The problem should be based on the following parameters:
{param_list}

## Expected Answer Constraint
The computed final result MUST numerically match:
{answer_para}

## Problem Construction Requirements
1. Scientific Accuracy:
   - Correctly apply the formula: {formula}
   - Maintain unit consistency; show conversions where non-trivial.
   - Select or invent a plausible scenario (experiment, natural process, or theoretical model) that justifies the formula’s use.
2. Logical Clarity:
   - Present a coherent narrative (e.g., reaction mechanism, energy balance, motion description).
   - If a chemical reaction is used, ensure it is balanced and physically consistent.
   - If a physics scenario is used, ensure forces, fields, or energies are plausible.
3. Presentation Quality:
   - Use precise technical language.
   - Embed equations in LaTeX: e.g., $F=ma$, $q=mc\Delta T$, $PV=nRT$.
   - Use appropriate significant figures (justify if rounding).
4. Do NOT:
   - Expose raw input parameter names.
   - Fully provide the formula itself that needs to be asked about.
   - Ask the user for additional data.
   - Include meta-instructions or placeholders in the final output.
   - Deviate from the provided answer value.

## Solution Requirements
- Show step-by-step derivation.
- Explicitly write the main governing formula before substitution.
- Show unit cancellation or transformation.
- Justify any approximations.
- Conclude by enclosing the final answer (that matches the target value) in \boxed{}.
- Both the generated questions and answers should be in English.

## Output JSON Format
Return ONLY a JSON object with the following keys:
{
  "question": "A fully self-contained, well-structured Physics or Physical Chemistry problem statement (with LaTeX math expressions).",
  "answer": "Detailed solution showing reasoning, substitutions, unit analysis, and final matching result.",
  "answer_units": "LaTeX-formatted unit expression (e.g., \text{mol·L}^{-1}, \text{kJ·mol}^{-1}, \text{Pa·s}); use 'dimensionless' if no unit."
}

## Additional Notes
- Prefer realistic constants (e.g., $R=8.314\ \text{J·mol}^{-1}\text{K}^{-1}$) unless the scenario mandates a specific variant.
- If assumptions (e.g., ideal gas, negligible heat loss, non-relativistic motion) are required, state them explicitly.
- The style should be professional and suitable for advanced undergraduate or early graduate level.

## Escaping requirement
- When showing LaTeX, JSON, file paths, or any string that normally contains backslashes, ensure each backslash is doubled (for example, write "\\Delta" for "\Delta", write "C:\\path\\my_file" for "C:\path\my_file").
- Validate final output to ensure no lone '\' characters remain; prefer double-escaping where ambiguity may occur.
"""

# G11_problem_filter
QUESTION_FILTER = r"""【任务】请判断下面的科学问题是否合理。合理性的判断需从以下几个方面进行：
1. 数值是否具有现实意义（如个数不能是小数、重量不能是负数、温度范围是否合理等）。  
2. 单位和量纲是否匹配（如速度不能用千克表示，分子数不应为负数）。  
3. 是否符合基本科学原理或常识（如物体运动速度不能超过光速，化学反应物质量守恒，生物个体数量不能为负等）。  

【问题】
{question}

请返回以下格式：
结论：YES 或 NO
理由：具体原因（简要说明问题合理或不合理的依据）。"""

# G12_normalization
NORMALIZE = r"""Convert all units in the following text to proper LaTeX format with these requirements:
- Keep the original question structure and content unchanged.
- Express all units, constants, chemical formulas, and symbols with superscripts using LaTeX syntax (e.g., $\text{g/cm}^3$, $\text{mol/L}$, \(\Delta k\), $\text{H}_2\text{O}$).
- Ensure the text remains a natural and coherent question.
- Return only the modified question, without any explanation or extra content.

Original text: 
{text}"""

# G13_teacher_physics
TEACHER = r"""{problem} {unit_sentence}
Please reason step by step, and put your final answer within $\boxed{}$ without including units."""

# G13_teacher_physics
UNIT_PHRASES = r"""The unit of the answer is {u}.
The answer's unit is {u}.
The unit for the answer is {u}.
The unit applicable to the answer is {u}.
The answer uses the unit {u}.
The unit corresponding to the answer is {u}.
The answer is expressed in the unit {u}.
The unit associated with the answer is {u}.
For the answer, the unit is {u}.
The unit that applies to the answer is {u}."""

PROMPT_SHA256 = {
    name: hashlib.sha256(template.encode("utf-8")).hexdigest()
    for name, template in {
        "FORMULAS": FORMULAS, "FORMULA_FILTER": FORMULA_FILTER, "CODE": CODE,
        "UNIT_TESTS": UNIT_TESTS, "PARAMETERS": PARAMETERS, "QUESTIONS": QUESTIONS,
        "QUESTION_FILTER": QUESTION_FILTER, "NORMALIZE": NORMALIZE,
        "TEACHER": TEACHER, "UNIT_PHRASES": UNIT_PHRASES,
    }.items()
}

def render(template, values):
    """Replace known placeholders once; leave JSON and LaTeX braces untouched."""
    pattern = re.compile("|".join(re.escape("{" + key + "}") for key in sorted(values, key=len, reverse=True)))
    return pattern.sub(lambda match: str(values[match.group()[1:-1]]), template)


def formula_values(formula, *, quoted=False, escaped=False):
    values = {"name": formula["name"], "formula": formula["expression"],
              "description": formula.get("description", ""), "applicable_range": formula["domain"]}
    if escaped:
        return {key: json.dumps(value, ensure_ascii=False)[1:-1] for key, value in values.items()}
    return {key: json.dumps(value, ensure_ascii=False) for key, value in values.items()} if quoted else values


def teacher(question, unit, *, seed=42):
    unit = unit.strip()
    unit_line = ""
    if unit and unit.lower() != "dimensionless":
        display = unit if unit.startswith("$") and unit.endswith("$") else "$" + unit + "$"
        phrase = random.Random(seed).choice(UNIT_PHRASES.splitlines())
        unit_line = render(phrase, {"u": display})
    return render(TEACHER, {"problem": question, "unit_sentence": unit_line}).strip()
