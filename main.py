from flask import Flask, request, jsonify
import xmlrpc.client
from datetime import datetime, date
import calendar # Necesitarás importar el módulo calendar
import os

app = Flask(__name__)

# Tu ruta existente para kilos por día
@app.route("/api/kilos_por_orden/csv", methods=["GET"])
def obtener_kilos_por_orden_csv():
    fecha_str = request.args.get("fecha")
    if not fecha_str:
        return "Falta la fecha", 400

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return "Formato de fecha incorrecto (YYYY-MM-DD)", 400

    url = os.environ.get("ODOO_URL")
    db = os.environ.get("ODOO_DB")
    username = os.environ.get("ODOO_USERNAME")
    password = os.environ.get("ODOO_PASSWORD")

    if not all([url, db, username, password]):
        return "Faltan las credenciales de Odoo en las variables de entorno", 500

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    try:
        uid = common.authenticate(db, username, password, {})
        if not uid:
            return "No se pudo autenticar con Odoo", 403
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    except Exception as e:
        return f"Error al conectar con Odoo: {e}", 500

    try:
        orders = models.execute_kw(
            db,
            uid,
            password,
            'pos.order',
            'search_read',
            [[
                ['date_order', '>=', f"{fecha} 00:00:00"],
                ['date_order', '<=', f"{fecha} 23:59:59"],
                ['state', 'in', ['done', 'registered', 'paid', 'invoiced']]
            ]],
            {'fields': ['config_id', 'x_studio_float_field_1u1_1irfgb3un']}
        )

        resultado = []
        for order in orders:
            nombre_sucursal = order['config_id'][1]
            total_kilos = order.get('x_studio_float_field_1u1_1irfgb3un', 0.0)

            if total_kilos > 0:
                resultado.append({
                    'fecha': fecha_str, # Esto seguirá siendo la fecha de la orden, pero la agruparemos por mes en Sheets
                    'sucursal': nombre_sucursal,
                    'kilos_total_orden': total_kilos
                })

        return jsonify(resultado)

    except Exception as e:
        return f"Error al procesar la solicitud: {e}", 500


# --- NUEVA RUTA para kilos por mes ---
@app.route("/api/kilos_por_mes/csv", methods=["GET"])
def obtener_kilos_por_mes_csv():
    mes_str = request.args.get("mes")
    anio_str = request.args.get("anio")

    if not mes_str or not anio_str:
        return "Faltan los parámetros 'mes' y/o 'anio'", 400

    try:
        mes = int(mes_str)
        anio = int(anio_str)
        if not (1 <= mes <= 12) or not (1900 <= anio <= 2100): # Rango de años razonable
            raise ValueError
    except ValueError:
        return "Formato de mes o año incorrecto (ej. mes=5, anio=2025)", 400

    # Calcular el primer y último día del mes
    primer_dia_mes = date(anio, mes, 1)
    ultimo_dia_mes = date(anio, mes, calendar.monthrange(anio, mes)[1])

    # Datos de acceso a Odoo
    url = os.environ.get("ODOO_URL")
    db = os.environ.get("ODOO_DB")
    username = os.environ.get("ODOO_USERNAME")
    password = os.environ.get("ODOO_PASSWORD")

    if not all([url, db, username, password]):
        return "Faltan las credenciales de Odoo en las variables de entorno", 500

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    try:
        uid = common.authenticate(db, username, password, {})
        if not uid:
            return "No se pudo autenticar con Odoo", 403
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    except Exception as e:
        return f"Error al conectar con Odoo: {e}", 500

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

        # Aquí acumularemos los kilos por sucursal para todo el mes
        kilos_por_sucursal_mensual = {}

        for order in orders:
            nombre_sucursal = order['config_id'][1].replace(/\s*\(.*\)/, '').strip() # Limpiamos el nombre aquí también
            total_kilos = order.get('x_studio_float_field_1u1_1irfgb3un', 0.0)

            if total_kilos > 0:
                if nombre_sucursal in kilos_por_sucursal_mensual:
                    kilos_por_sucursal_mensual[nombre_sucursal] += total_kilos
                else:
                    kilos_por_sucursal_mensual[nombre_sucursal] = total_kilos
        
        # Convertimos el diccionario a un formato de lista para el JSON
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
        return f"Error al procesar la solicitud mensual: {e}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
