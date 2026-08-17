import math

import pytest

from app.guardrails.safe_calculator import safe_calculate


class TestBasicMath:
    def test_addition(self):
        r = safe_calculate("2 + 2")
        assert r.ok
        assert r.value == 4

    def test_percent_change(self):
        r = safe_calculate("(152.3 - 148.9) / 148.9 * 100")
        assert r.ok
        assert round(r.value, 4) == round((152.3 - 148.9) / 148.9 * 100, 4)

    def test_negative_numbers(self):
        r = safe_calculate("-5 + 3")
        assert r.ok
        assert r.value == -2

    def test_parentheses_and_precedence(self):
        r = safe_calculate("2 + 3 * 4")
        assert r.ok
        assert r.value == 14

    def test_power(self):
        r = safe_calculate("2 ** 10")
        assert r.ok
        assert r.value == 1024

    def test_floor_div_and_mod(self):
        assert safe_calculate("7 // 2").value == 3
        assert safe_calculate("7 % 2").value == 1

    def test_allowed_functions(self):
        assert safe_calculate("abs(-5)").value == 5
        assert safe_calculate("round(3.14159, 2)").value == 3.14
        assert safe_calculate("min(3, 1, 2)").value == 1
        assert safe_calculate("max(3, 1, 2)").value == 3
        assert math.isclose(safe_calculate("sqrt(16)").value, 4.0)


class TestErrorHandling:
    def test_empty_expression(self):
        r = safe_calculate("")
        assert not r.ok

    def test_none_expression(self):
        r = safe_calculate(None)
        assert not r.ok

    def test_division_by_zero(self):
        r = safe_calculate("1 / 0")
        assert not r.ok
        assert "zero" in r.error.lower()

    def test_syntax_error(self):
        r = safe_calculate("2 + * 3")
        assert not r.ok

    def test_too_long_expression(self):
        r = safe_calculate("1+" * 200 + "1")
        assert not r.ok

    def test_huge_exponent_rejected(self):
        r = safe_calculate("2 ** 99999999")
        assert not r.ok


class TestCodeInjectionRejection:
    """These must ALL fail -- this is the security boundary of the tool."""

    def test_rejects_import(self):
        r = safe_calculate("__import__('os').system('echo pwned')")
        assert not r.ok

    def test_rejects_os_system_direct(self):
        r = safe_calculate("os.system('rm -rf /')")
        assert not r.ok

    def test_rejects_open_file(self):
        r = safe_calculate("open('/etc/passwd').read()")
        assert not r.ok

    def test_rejects_name_lookup(self):
        r = safe_calculate("x")
        assert not r.ok

    def test_rejects_attribute_access(self):
        r = safe_calculate("(1).__class__")
        assert not r.ok

    def test_rejects_dunder_class_chain(self):
        r = safe_calculate("().__class__.__bases__[0].__subclasses__()")
        assert not r.ok

    def test_rejects_lambda(self):
        r = safe_calculate("(lambda: 1)()")
        assert not r.ok

    def test_rejects_list_comprehension(self):
        r = safe_calculate("[x for x in range(10)]")
        assert not r.ok

    def test_rejects_string_literal(self):
        r = safe_calculate("'hello'")
        assert not r.ok

    def test_rejects_disallowed_function_call(self):
        r = safe_calculate("eval('1+1')")
        assert not r.ok

    def test_rejects_exec_call(self):
        r = safe_calculate("exec('import os')")
        assert not r.ok

    def test_rejects_getattr(self):
        r = safe_calculate("getattr(1, '__class__')")
        assert not r.ok

    def test_rejects_keyword_args_to_allowed_func(self):
        r = safe_calculate("round(3.14159, ndigits=2)")
        assert not r.ok

    def test_rejects_semicolon_statements(self):
        r = safe_calculate("1; import os")
        assert not r.ok

    def test_rejects_assignment(self):
        r = safe_calculate("x = 5")
        assert not r.ok

    def test_rejects_walrus(self):
        r = safe_calculate("(x := 5)")
        assert not r.ok

    def test_rejects_subscript(self):
        r = safe_calculate("[1,2,3][0]")
        assert not r.ok

    def test_rejects_boolean_constants(self):
        r = safe_calculate("True + 1")
        assert not r.ok

    def test_rejects_f_string(self):
        r = safe_calculate("f'{1+1}'")
        assert not r.ok
