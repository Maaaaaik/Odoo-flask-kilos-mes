from flask import Flask, request, jsonify
import xmlrpc.client
from datetime import datetime, date
import calendar
import os
import re  # ¡Importante: el módulo para expresiones regulares!

app = Flask(__name__)

@app.route("/api/kilos_por_mes/csv", methods=["GET"])
def obtener_kilos_por_mes_csv():
    """
    Obtiene el total de kilos vendidos por sucursal para un mes y año específicos desde Odoo.
    Requiere 'mes' y 'anio' como parámetros de query.
    """
    mes_str = request.args.get("mes")
    anio_str = request.args.get("anio")

    if not mes_str or not anio_str:
        return "Faltan los parámetros 'mes' y/o 'anio'", 400

    try:
        mes = int(mes_str)
        anio = int(anio_str)
        if not (1 <= mes <= 12) or not (1900 <= anio <= 2100):
            raise ValueError("Mes o año fuera de rango válido.")
    except ValueError as e:
        return f"Formato de mes o año incorrecto (ej. mes=5, anio=2025). Error: {e}", 400

    # Calcular el primer y último día del mes
    primer_dia_mes = date(anio, mes, 1)
    ultimo_dia_mes = date(anio, mes, calendar.monthrange(anio, mes)[1])

    # Datos de acceso a Odoo desde variables de entorno
    url = os.environ.get("ODOO_URL")
    db = os.environ.get("ODOO_DB")
    username = os.environ.get("ODOO_USERNAME")
    password = os.environ.get("ODOO_PASSWORD")

    if not all([url, db, username, password]):
        return "Faltan las credenciales de Odoo en las variables de entorno (ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)", 500

    # Conexión y autenticación con Odoo
    try:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db, username, password, {})
        if not uid:
            return "No se pudo autenticar con Odoo. Verifica tus credenciales.", 403
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    except Exception as e:
        return f"Error al conectar con Odoo: {e}", 500

    # Obtener órdenes de venta del mes
    try:
        orders = models.execute_kw(
            db,
            uid,
            password,
            'pos.order',
            'search_read',
            [[
                ['date_order', '>=', f"{primer_dia_mes} 00:00:00"],
                ['date_order', '<=', f"{ultimo_dia_mes} 23:59:59"],
                ['state', 'in', ['done', 'registered', 'paid', 'invoiced']]
            ]],
            {'fields': ['config_id', 'x_studio_float_field_1u1_1irfgb3un']}
        )

        # Acumular los kilos por sucursal para todo el mes
        kilos_por_sucursal_mensual = {}

        for order in orders:
            # ¡Línea corregida! Usando re.sub para expresiones regulares en Python
            nombre_sucursal = re.sub(r'\s*\(.*\)', '', order['config_id'][1]).strip()
            total_kilos = order.get('x_studio_float_field_1u1_1irfgb3un', 0.0)

            if total_kilos > 0:
                kilos_por_sucursal_mensual[nombre_sucursal] = kilos_por_sucursal_mensual.get(nombre_sucursal, 0.0) + total_kilos
        
        # Formatear el resultado como una lista de diccionarios para JSON
        resultado_mensual = []
        for sucursal, kilos in kilos_por_sucursal_mensual.items():
            resultado_mensual.append({
                'mes': mes,
                'anio': anio,
                'sucursal': sucursal,
                'kilos_total_mes': kilos
            })

        return jsonify(resultado_mensual)

    except Exception as e:
        return f"Error al procesar la solicitud mensual desde Odoo: {e}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
