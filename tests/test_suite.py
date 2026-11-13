"""End-to-end automated test suite for Smart Talent backend, ML API, and UI/UX invariants."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / 'dashboard'
SRC_API_PATH = REPO_ROOT / 'src' / 'api.py'

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import server as dashboard_server  # noqa: E402


def _load_src_api_module():
    spec = importlib.util.spec_from_file_location('smart_talent_src_api', SRC_API_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


src_api = _load_src_api_module()


def asgi_request(
    app,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    json_body: dict | None = None,
) -> tuple[int, dict[str, str], dict | list | str | None]:
    """Invoke a FastAPI ASGI app in-process without requiring httpx."""
    raw_body = json.dumps(json_body).encode('utf-8') if json_body is not None else b''
    query_string = urlencode(query or {}).encode('ascii')
    headers = [(b'host', b'testserver')]
    if json_body is not None:
        headers.append((b'content-type', b'application/json'))

    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': method.upper(),
        'scheme': 'http',
        'path': path,
        'raw_path': path.encode('ascii'),
        'query_string': query_string,
        'headers': headers,
        'client': ('127.0.0.1', 50000),
        'server': ('testserver', 80),
    }

    sent_body = False

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {'type': 'http.request', 'body': raw_body, 'more_body': False}
        return {'type': 'http.disconnect'}

    status_code = 500
    response_headers: dict[str, str] = {}
    body_chunks: list[bytes] = []

    async def send(message):
        nonlocal status_code
        if message['type'] == 'http.response.start':
            status_code = message['status']
            for key, val in message.get('headers', []):
                response_headers[key.decode('latin-1').lower()] = val.decode('latin-1')
        elif message['type'] == 'http.response.body':
            body_chunks.append(message.get('body', b''))

    asyncio.run(app(scope, receive, send))
    raw_text = b''.join(body_chunks).decode('utf-8')
    if not raw_text:
        return status_code, response_headers, None
    try:
        return status_code, response_headers, json.loads(raw_text)
    except json.JSONDecodeError:
        return status_code, response_headers, raw_text


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    match = re.search(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b', value)
    if not match:
        return None
    hx = match.group(1)
    if len(hx) == 3:
        hx = ''.join(ch * 2 for ch in hx)
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _extract_css_vars(css: str) -> dict[str, str]:
    root_match = re.search(r':root\s*\{([^}]*)\}', css, re.DOTALL)
    if not root_match:
        return {}
    return {
        k.strip(): v.strip()
        for k, v in re.findall(r'(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);', root_match.group(1))
    }


def _resolve_css_color(value: str, css_vars: dict[str, str]) -> tuple[int, int, int] | None:
    resolved = value.strip()
    for _ in range(4):
        var_match = re.search(r'var\((--[a-zA-Z0-9_-]+)\)', resolved)
        if not var_match:
            break
        replacement = css_vars.get(var_match.group(1), '')
        resolved = resolved.replace(var_match.group(0), replacement)
    return _parse_hex_color(resolved)


def _extract_css_properties(css_clean: str, selector: str) -> dict[str, str]:
    pattern = re.compile(rf'(?:^|[}}{{\s]){re.escape(selector)}\s*\{{([^}}]*)\}}', re.MULTILINE | re.DOTALL)
    props: dict[str, str] = {}
    for block in pattern.findall(css_clean):
        for k, v in re.findall(r'([a-zA-Z-]+)\s*:\s*([^;]+);', block):
            props[k.strip().lower()] = v.strip()
    return props


FORBIDDEN_UNTRANSLATED_API_TOKENS = (
    'Francia',
    'Alemania',
    'España',
    'Italia',
    'Nueva Zelanda',
    'SudAfrica',
    'Arabia Saudí',
    'First Class',
    'Second Class',
    'Standard Class',
    'Same Day',
    'Western Europe',
    'Eastern Europe',
    'Northern Europe',
    'Southern Europe',
    'Central America',
    'South America',
    'East of USA',
    'West of USA',
    'South of USA',
    'US Center',
)


class TestDashboardServerEndpoints(unittest.TestCase):
    """End-to-end tests for Grupo8-Smart-Talent/dashboard/server.py."""

    def test_overview_all_and_macro_regions_pt_br(self):
        status, _, data = asgi_request(dashboard_server.app, 'GET', '/api/overview', {'region': 'Todas'})
        self.assertEqual(status, 200)
        self.assertEqual(data['rows'], 180519)
        self.assertEqual(data['unique_orders'], 65752)
        self.assertGreater(data['late_risk_pct'], 0)
        self.assertGreater(data['avg_delay_days'], 0)
        self.assertEqual(
            data['available_regions'],
            ['Todas', 'América do Norte', 'Europa', 'Ásia', 'América do Sul', 'Oceania', 'África'],
        )
        serialized = json.dumps(data, ensure_ascii=False)
        for token in FORBIDDEN_UNTRANSLATED_API_TOKENS:
            self.assertNotIn(token, serialized)

        macro_sum = 0
        for reg in ['América do Norte', 'Europa', 'Ásia', 'América do Sul', 'Oceania', 'África']:
            st, _, reg_data = asgi_request(dashboard_server.app, 'GET', '/api/overview', {'region': reg})
            self.assertEqual(st, 200)
            self.assertGreater(reg_data['rows'], 0, f'Expected rows > 0 for {reg}')
            self.assertGreater(reg_data['unique_orders'], 0)
            macro_sum += reg_data['rows']
        self.assertEqual(macro_sum, 180519)

        st_empty, _, empty_data = asgi_request(
            dashboard_server.app, 'GET', '/api/overview', {'region': 'RegiaoInexistente'}
        )
        self.assertEqual(st_empty, 200)
        self.assertEqual(empty_data['rows'], 0)
        self.assertEqual(empty_data['unique_orders'], 0)
        self.assertEqual(empty_data['regions'], [])

    def test_routes_summary_sorting_pt_br_and_compatibility(self):
        for sort_by in ('impact', 'risk', 'volume', 'loss', 'avg_delay'):
            status, _, data = asgi_request(
                dashboard_server.app,
                'GET',
                '/api/routes',
                {'region': 'Todas', 'mode': 'Todas', 'sort_by': sort_by},
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(data['routes']), 15)
            self.assertEqual(data['summary']['lines'], 180519)
            self.assertEqual(data['summary']['orders'], 65752)
            self.assertEqual(
                set(data['shipping_modes']),
                {'Primeira Classe', 'Segunda Classe', 'Classe Padrão', 'Mesmo Dia'},
            )
            self.assertEqual(data['sort_by'], sort_by)

            serialized = json.dumps(data, ensure_ascii=False)
            for token in FORBIDDEN_UNTRANSLATED_API_TOKENS:
                self.assertNotIn(token, serialized)

            first = data['routes'][0]
            for key in (
                'order region',
                'order country',
                'orders',
                'unique_orders',
                'risk_pct',
                'avg_delay',
                'sales',
                'profit',
                'negative_profit_loss_usd',
            ):
                self.assertIn(key, first)
            if sort_by in ('impact', 'risk'):
                self.assertGreaterEqual(first['orders'], 50)

        # Filtering by PT-BR mode or original CSV mode yields identical results
        st_pt, _, pt_data = asgi_request(
            dashboard_server.app,
            'GET',
            '/api/routes',
            {'region': 'Europa', 'mode': 'Primeira Classe', 'sort_by': 'impact'},
        )
        st_en, _, en_data = asgi_request(
            dashboard_server.app,
            'GET',
            '/api/routes',
            {'region': 'Europa', 'mode': 'First Class', 'sort_by': 'impact'},
        )
        self.assertEqual(st_pt, 200)
        self.assertEqual(st_en, 200)
        self.assertEqual(pt_data['summary'], en_data['summary'])
        self.assertEqual(len(pt_data['shipping_modes']), 4)
        self.assertGreater(pt_data['summary']['risk_pct'], 90.0)

        st_empty, _, empty_data = asgi_request(
            dashboard_server.app,
            'GET',
            '/api/routes',
            {'region': 'Europa', 'mode': 'ModalidadeInexistente'},
        )
        self.assertEqual(st_empty, 200)
        self.assertEqual(empty_data['routes'], [])
        self.assertEqual(empty_data['summary']['lines'], 0)
        self.assertEqual(len(empty_data['shipping_modes']), 4)

    def test_bi_endpoint_pt_br_and_capitalization(self):
        status, _, data = asgi_request(dashboard_server.app, 'GET', '/api/bi')
        self.assertEqual(status, 200)
        self.assertEqual(data['observed']['lines'], 180519)
        self.assertEqual(data['observed']['orders'], 65752)
        self.assertEqual(len(data['observed']['top_products']), 8)
        self.assertIn('data_sources', data)
        self.assertIn('recommendations', data)
        self.assertIn('warning', data)

        serialized = json.dumps(data, ensure_ascii=False)
        for token in FORBIDDEN_UNTRANSLATED_API_TOKENS:
            self.assertNotIn(token, serialized)

        for rec in data['recommendations']:
            self.assertIn(rec['kind'], ('Observado', 'Hipótese', 'Dado Faltante'))
            self.assertRegex(rec['title'], r'^[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]')

    def test_scenario_valid_and_validation_errors(self):
        status, _, data = asgi_request(
            dashboard_server.app,
            'POST',
            '/api/scenario',
            json_body={'eu_demand_share': 0.3, 'delay_reduction_days': 1.0, 'cost_per_order': 2.0},
        )
        self.assertEqual(status, 200)
        self.assertIn('observed_europe_avg_delay_days', data)
        self.assertAlmostEqual(
            data['applied_delay_reduction_days'],
            min(1.0, data['observed_europe_avg_delay_days']),
            places=2,
        )

        st_bad_share, _, err_share = asgi_request(
            dashboard_server.app,
            'POST',
            '/api/scenario',
            json_body={'eu_demand_share': 1.5, 'delay_reduction_days': 1.0, 'cost_per_order': 0},
        )
        self.assertEqual(st_bad_share, 400)
        self.assertEqual(err_share['error']['code'], 'invalid_input')

        st_bad_days, _, err_days = asgi_request(
            dashboard_server.app,
            'POST',
            '/api/scenario',
            json_body={'eu_demand_share': 0.3, 'delay_reduction_days': 99, 'cost_per_order': 0},
        )
        self.assertEqual(st_bad_days, 400)
        self.assertEqual(err_days['error']['code'], 'invalid_input')

    def test_predict_options_pt_br_and_alias(self):
        for endpoint in ('/api/predict-options', '/api/predict/options'):
            status, _, data = asgi_request(dashboard_server.app, 'GET', endpoint)
            self.assertEqual(status, 200)
            self.assertTrue(data['model_available'])
            self.assertEqual(set(data['shipping_modes']), set(dashboard_server.SHIPPING_MODE_PT_BR.values()))
            self.assertEqual(set(data['regions']), set(dashboard_server.REGION_PT_BR.values()))
            self.assertEqual(set(data['countries']), set(dashboard_server.COUNTRY_PT_BR.values()))
            self.assertEqual(set(data['categories']), set(dashboard_server.CATEGORY_PT_BR.values()))
            self.assertEqual(len(data['products']), 20)
            self.assertIn('regions_countries', data)
            self.assertIn('categories_products', data)
            self.assertGreaterEqual(len(data['presets']), 2)

            serialized = json.dumps(data, ensure_ascii=False)
            for token in FORBIDDEN_UNTRANSLATED_API_TOKENS:
                self.assertNotIn(token, serialized)

            for prod in data['products']:
                self.assertIn(prod['category_name'], data['categories'])

    def test_predict_pt_br_compatibility_validation_and_503(self):
        _, _, opts = asgi_request(dashboard_server.app, 'GET', '/api/predict-options')
        for preset in opts['presets']:
            status, _, pred = asgi_request(
                dashboard_server.app, 'POST', '/api/predict', json_body=preset['payload']
            )
            self.assertEqual(status, 200)
            self.assertTrue(pred['available'])
            self.assertIn(pred['late_delivery_risk'], (0, 1))
            self.assertGreaterEqual(pred['probability'], 0.0)
            self.assertLessEqual(pred['probability'], 1.0)
            self.assertIn(pred['risk_level'], ('Alto', 'Moderado', 'Baixo'))
            self.assertRegex(pred['risk_label'], r'^[A-ZÁÉÍÓÚÂÊÔÃÕÇ]')
            self.assertIn('interpretation', pred)

        # PT-BR payload must yield identical probability to original CSV payload
        pt_payload = {
            'shipping_mode': 'Primeira Classe',
            'order_region': 'Europa Ocidental',
            'order_country': 'França',
            'category_name': 'Pesca',
            'product_name': 'Field & Stream Sportsman 16 Gun Fire Safe',
            'scheduled_days': 1,
            'quantity': 1,
            'product_price': 399.98,
            'order_month': 11,
            'order_weekday': 2,
        }
        orig_payload = {
            'shipping_mode': 'First Class',
            'order_region': 'Western Europe',
            'order_country': 'Francia',
            'category_name': 'Fishing',
            'product_name': 'Field & Stream Sportsman 16 Gun Fire Safe',
            'scheduled_days': 1,
            'quantity': 1,
            'product_price': 399.98,
            'order_month': 11,
            'order_weekday': 2,
        }
        st_pt, _, pred_pt = asgi_request(dashboard_server.app, 'POST', '/api/predict', json_body=pt_payload)
        st_orig, _, pred_orig = asgi_request(dashboard_server.app, 'POST', '/api/predict', json_body=orig_payload)
        self.assertEqual(st_pt, 200)
        self.assertEqual(st_orig, 200)
        self.assertEqual(pred_pt['probability'], pred_orig['probability'])
        self.assertEqual(pred_pt['late_delivery_risk'], pred_orig['late_delivery_risk'])

        # Region and category normalization for training strings containing extra spaces
        norm_payload = {
            'shipping_mode': 'Primeira Classe',
            'order_region': 'Sul dos EUA',
            'order_country': 'Estados Unidos',
            'category_name': 'Visto na TV',
            'product_name': 'Perfect Fitness Perfect Rip Deck',
            'scheduled_days': 1,
            'quantity': 1,
            'product_price': 59.99,
            'order_month': 10,
            'order_weekday': 3,
        }
        st_norm, _, pred_norm = asgi_request(
            dashboard_server.app, 'POST', '/api/predict', json_body=norm_payload
        )
        self.assertEqual(st_norm, 200)
        self.assertTrue(pred_norm['available'])

        # Validation error -> HTTP 400
        bad_payload = {**opts['presets'][0]['payload'], 'order_month': 13}
        st_bad, _, err_bad = asgi_request(
            dashboard_server.app, 'POST', '/api/predict', json_body=bad_payload
        )
        self.assertEqual(st_bad, 400)
        self.assertEqual(err_bad['error']['code'], 'invalid_input')

        # Missing model -> HTTP 503 without crashing
        original_path = dashboard_server.MODEL_PATH
        try:
            dashboard_server.load_prediction_bundle.cache_clear()
            dashboard_server.MODEL_PATH = dashboard_server.ROOT / '__missing_model__.joblib'

            st_opt503, _, opt503 = asgi_request(dashboard_server.app, 'GET', '/api/predict-options')
            self.assertEqual(st_opt503, 200)
            self.assertFalse(opt503['model_available'])

            st_503, _, err_503 = asgi_request(
                dashboard_server.app, 'POST', '/api/predict', json_body=opts['presets'][0]['payload']
            )
            self.assertEqual(st_503, 503)
            self.assertIn('detail', err_503)
            self.assertEqual(err_503['error']['code'], 'model_unavailable')
        finally:
            dashboard_server.MODEL_PATH = original_path
            dashboard_server.load_prediction_bundle.cache_clear()


class TestSrcPredictionAPI(unittest.TestCase):
    """End-to-end tests for Grupo8-Smart-Talent/src/api.py."""

    def test_health_and_predict(self):
        st_h, _, health = asgi_request(src_api.app, 'GET', '/health')
        self.assertEqual(st_h, 200)
        self.assertEqual(health['status'], 'ok')
        self.assertTrue(health['model_exists'])

        payload = {
            'shipping_mode': 'First Class',
            'order_region': 'Western Europe',
            'order_country': 'Francia',
            'category_name': 'Fishing',
            'product_name': 'Field & Stream Sportsman 16 Gun Fire Safe',
            'scheduled_days': 1,
            'quantity': 1,
            'product_price': 399.98,
            'order_month': 11,
            'order_weekday': 2,
        }
        st_p, _, pred = asgi_request(src_api.app, 'POST', '/predict', json_body=payload)
        self.assertEqual(st_p, 200)
        self.assertIn(pred['late_delivery_risk'], (0, 1))
        self.assertGreaterEqual(pred['probability'], 0.0)
        self.assertLessEqual(pred['probability'], 1.0)
        self.assertIn('interpretation', pred)

        bad_payload = {k: v for k, v in payload.items() if k != 'order_month'}
        st_422, _, _ = asgi_request(src_api.app, 'POST', '/predict', json_body=bad_payload)
        self.assertEqual(st_422, 422)

        original_path = src_api.MODEL_PATH
        try:
            src_api.MODEL_PATH = src_api.MODEL_PATH.parent / '__missing_model__.joblib'
            st_503, _, err_503 = asgi_request(src_api.app, 'POST', '/predict', json_body=payload)
            self.assertEqual(st_503, 503)
            self.assertIn('detail', err_503)
        finally:
            src_api.MODEL_PATH = original_path


class TestDashboardUIInvariants(unittest.TestCase):
    """Static UI/UX invariants across dashboard/index.html, styles.css, and app.js."""

    @classmethod
    def setUpClass(cls):
        cls.html = (DASHBOARD_DIR / 'index.html').read_text(encoding='utf-8')
        cls.css = (DASHBOARD_DIR / 'styles.css').read_text(encoding='utf-8')
        cls.js = (DASHBOARD_DIR / 'app.js').read_text(encoding='utf-8')

    def test_all_js_ids_exist_in_html(self):
        html_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', self.html))
        js_ids = set(
            re.findall(r'getElementById\(\s*["\']([A-Za-z_][A-Za-z0-9_-]*)["\']', self.js)
        ) | set(
            re.findall(r'querySelector(?:All)?\(\s*["\']#([A-Za-z_][A-Za-z0-9_-]*)', self.js)
        )
        self.assertGreater(len(js_ids), 20)
        missing = sorted(js_ids - html_ids)
        self.assertEqual(missing, [], f'IDs referenced in app.js missing from index.html: {missing}')

    def test_no_draft_dead_or_untranslated_ui_tokens(self):
        forbidden_everywhere = (
            'Visualização conceitual',
            'A tabela final deve usar',
            'Rota ilustrativa',
            'carregar rota do CSV',
            '♧',
            'Late_delivery_risk',
            'lead time',
        )
        for token in forbidden_everywhere:
            self.assertNotIn(token, self.html, f'Found forbidden token "{token}" in index.html')
            self.assertNotIn(token, self.js, f'Found forbidden token "{token}" in app.js')

        for mode_token in ('First Class', 'Second Class', 'Standard Class', 'Same Day'):
            self.assertNotIn(mode_token, self.html, f'Found untranslated mode "{mode_token}" in index.html')

    def test_cache_busting_and_single_row_nav_layout(self):
        self.assertRegex(self.html, r'styles\.css\?v=ux-exec-3')
        self.assertRegex(self.html, r'app\.js\?v=ux-exec-3')

        css_clean = re.sub(r'/\*.*?\*/', '', self.css, flags=re.DOTALL)
        nav_props = _extract_css_properties(css_clean, '.nav')
        self.assertEqual(
            nav_props.get('flex-wrap'),
            'nowrap',
            '.nav must enforce flex-wrap: nowrap so the 6 navigation buttons stay on one horizontal row',
        )

    def test_html_microcopy_capitalization(self):
        for tag in ('small', 'option'):
            for text in re.findall(rf'<{tag}[^>]*>([^<]+)</{tag}>', self.html):
                clean = text.strip()
                if not clean:
                    continue
                self.assertNotRegex(
                    clean,
                    r'^[a-záéíóúâêôãõç]',
                    f'<{tag}> text starts with lowercase: "{clean}"',
                )
        for cls_name in ('tag', 'note'):
            for text in re.findall(
                rf'<[a-z]+\s+[^>]*class="[^"]*\b{cls_name}\b[^"]*"[^>]*>([^<]+)</[a-z]+>',
                self.html,
            ):
                clean = text.strip()
                if not clean:
                    continue
                self.assertNotRegex(
                    clean,
                    r'^[a-záéíóúâêôãõç]',
                    f'.{cls_name} text starts with lowercase: "{clean}"',
                )

    def test_proposal_contrast_and_no_dark_bg_gray_text_regression(self):
        css_clean = re.sub(r'/\*.*?\*/', '', self.css, flags=re.DOTALL)
        css_vars = _extract_css_vars(css_clean)

        proposal_props = _extract_css_properties(css_clean, '.proposal')
        proposal_p_props = _extract_css_properties(css_clean, '.proposal p')
        proposal_h2_props = _extract_css_properties(css_clean, '.proposal h2')
        card_p_props = _extract_css_properties(css_clean, '.card > p')

        bg_raw = proposal_props.get('background') or proposal_props.get('background-color') or ''
        bg_rgb = _resolve_css_color(bg_raw, css_vars)
        self.assertIsNotNone(bg_rgb, f'Could not parse .proposal background color from "{bg_raw}"')

        self.assertNotEqual(bg_raw.lower(), '#2a4b39')

        p_color_raw = proposal_p_props.get('color') or proposal_props.get('color') or ''
        p_rgb = _resolve_css_color(p_color_raw, css_vars)
        self.assertIsNotNone(p_rgb, f'Could not parse .proposal p text color from "{p_color_raw}"')
        self.assertNotEqual(p_color_raw.lower(), '#5f5a54')

        if 'color' in card_p_props and 'color' not in proposal_p_props:
            card_p_rgb = _resolve_css_color(card_p_props['color'], css_vars)
            self.assertIsNotNone(card_p_rgb)
            self.assertGreaterEqual(
                _contrast_ratio(card_p_rgb, bg_rgb),
                4.5,
                '.card > p color overrides .proposal text without sufficient contrast',
            )

        p_ratio = _contrast_ratio(p_rgb, bg_rgb)
        self.assertGreaterEqual(
            p_ratio,
            4.5,
            f'.proposal p contrast ratio {p_ratio:.2f} is below WCAG AA (4.5:1)',
        )

        h2_color_raw = proposal_h2_props.get('color') or proposal_props.get('color') or ''
        h2_rgb = _resolve_css_color(h2_color_raw, css_vars)
        self.assertIsNotNone(h2_rgb, f'Could not parse .proposal h2 color from "{h2_color_raw}"')
        h2_ratio = _contrast_ratio(h2_rgb, bg_rgb)
        self.assertGreaterEqual(
            h2_ratio,
            3.0,
            f'.proposal h2 contrast ratio {h2_ratio:.2f} is below WCAG AA large text (3.0:1)',
        )


if __name__ == '__main__':
    unittest.main()
