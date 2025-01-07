from flask import Flask, render_template, request, jsonify
import psycopg2

app = Flask(__name__)

DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'samsung799',
    'host': 'localhost',
    'port': '5432'
}

#Fetch products with optional search, category and order
def fetch_products(search_query=None, category_type=None, filters=None, order_by=None, page=1, per_page=40):
    """Fetch products from the database with optional search, category, and order."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT id, name, price, discount_price, image, category, url, store_id, lowest_price, discount_percentage
            FROM product
            WHERE is_active = TRUE
        """
        params = []

        if search_query:
            query += " AND (name ILIKE %s OR category ILIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        if category_type:
            if category_type == "Svētkiem":
                query += """ 
                    AND ((category2 = 'Taviem svētkiem' AND store_id = 1) OR 
                    (category = 'Mājai un atpūtai' AND (category2 = 'Svētkiem' OR category2 = 'Ziemassvētku preces') AND store_id = 2))"""
            elif category_type == "Vegānu":
                query += """
                    AND ((category = 'Vegāniem un veģetāriešiem' AND store_id = 1) OR
                        (category = 'Bakaleja' AND category2 = 'Speciālā pārtika' AND category3 = 'Vegāniem un veģetāriešiem' AND store_id = 2))"""
            elif category_type == "Gaļa, zivis un gatavā kulinārija":
                query += " AND (category = 'Gaļa, zivis un gatavā kulinārija' OR category = 'Gaļa, zivs un gatavā kulinārija' OR category = 'Gatavots Rimi')"
            elif category_type == "Maize un konditoreja":
                query += " AND (category = 'Maize un konditoreja' OR category = 'Maize un konditorejas izstrādājumi')"
            elif category_type == "Saldētā pārtika":
                query += " AND (category = 'Saldētie ēdieni' OR category = 'Saldētā pārtika')"
            elif category_type == "Iepakotā pārtika":
                query += " AND (category = 'Iepakotā pārtika' OR category = 'Bakaleja')"
            elif category_type == "Saldumi un uzkodas":
                query += " AND (category = 'Saldumi un uzkodas' OR (category = 'Bakaleja' and category2 = 'Saldumi'))"
            elif category_type == "Dzērieni":
                query += " AND (category = 'Dzērieni' AND category2 NOT IN ('Alus, sidri un kokteiļi', 'Vīni', 'Stiprie alkoholiskie dzērieni'))"
            elif category_type == "Alkoholiskie dzērieni":
                query += " AND (category2 IN ('Alkoholiskie dzērieni', 'Stiprie alkoholiskie dzērieni', 'Alus, sidri un kokteiļi'))"
            elif category_type == "Vīns":
                query += " AND (category2 IN ('Vīna dārzs', 'Karstvīns un karstie dzērieni', 'Vīni'))"
            elif category_type == "Skaistumkopšanai un higiēnai":
                query += " AND (category IN ('Skaistumkopšanai un higiēnai', 'Kosmētika un higiēna'))"
            elif category_type == "Zīdaiņiem un bērniem":
                query += " AND (category IN ('Zīdaiņiem un bērniem', 'Zīdaiņu un bērnu preces'))"
            elif category_type == "Sadzīves ķīmija":
                query += " AND (category = 'Sadzīves ķīmija' OR (category = 'Viss tīrīšanai un mājdzīvniekiem' AND category2 != 'Mājdzīvnieku preces'))"
            elif category_type == "Mājdzīvniekiem":
                query += " AND (category = 'Mājdzīvniekiem' OR (category = 'Viss tīrīšanai un mājdzīvniekiem' AND category2 = 'Mājdzīvnieku preces'))"
            elif category_type == "Mājai":
                query += " AND category IN ('Mājai, dārzam un atpūtai', 'Mājai un atpūtai')"
            elif category_type == "Pakalpojumi":
                query += " AND category2 = 'Pakalpojumi'"
            elif category_type:
                query += " AND category = %s"
                params.append(category_type)

        if filters:
            #Separate store filters fom other for inclusive store filter
            store_filters = []
            other_filters = []
            for filter_type in filters:
                if filter_type in ["Rimi", "Barbora"]:
                    store_filters.append(filter_type)
                else:
                    other_filters.append(filter_type)
            
            if store_filters:
                store_ids = []
                if "Rimi" in store_filters:
                    store_ids.append(1)
                if "Barbora" in store_filters:
                    store_ids.append(2)
                if store_ids:
                    store_conditions = " OR ".join([f"store_id = {id}" for id in store_ids])
                    query += f" AND ({store_conditions})"
            
            for filter_type in other_filters:
                if filter_type == "Atlaide":
                    query += " AND (discount_price IS NOT NULL OR old_price > price)"

        if order_by == "name_asc":
            query += " ORDER BY name"
        elif order_by == "name_desc":
            query += " ORDER BY name DESC"
        elif order_by == "price_asc":
            query += " ORDER BY price ASC"
        elif order_by == "price_desc":
            query += " ORDER BY price DESC"
        elif order_by == "none":
            pass
        else:
            query += " ORDER BY name"

        #Pagination logic
        offset = (page - 1) * per_page
        query += f" LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        products = cursor.fetchall()

        count_query = """
            SELECT COUNT(*)
            FROM product
            WHERE is_active = TRUE
        """
        count_params = []

        #Apply search for total count
        if search_query:
            count_query += " AND (name ILIKE %s OR category ILIKE %s)"
            count_params.extend([f"%{search_query}%", f"%{search_query}%"])

        #Apply category for total count
        if category_type:
            if category_type == "Svētkiem":
                count_query += """ 
                    AND ((category2 = 'Taviem svētkiem' AND store_id = 1) OR 
                        (category = 'Mājai un atpūtai' AND (category2 = 'Svētkiem' OR category2 = 'Ziemassvētku preces') AND store_id = 2))"""
            elif category_type == "Vegānu":
                count_query += """
                    AND ((category = 'Vegāniem un veģetāriešiem' AND store_id = 1) OR
                        (category = 'Bakaleja' AND category2 = 'Speciālā pārtika' AND category3 = 'Vegāniem un veģetāriešiem' AND store_id = 2))"""
            elif category_type == "Gaļa, zivis un gatavā kulinārija":
                count_query += " AND (category = 'Gaļa, zivis un gatavā kulinārija' OR category = 'Gatavots Rimi')"
            elif category_type == "Maize un konditoreja":
                count_query += " AND (category = 'Maize un konditoreja' OR category = 'Maize un konditorejas izstrādājumi')"
            elif category_type == "Saldētā pārtika":
                count_query += " AND (category = 'Saldētie ēdieni' OR category = 'Saldētā pārtika')"
            elif category_type == "Iepakotā pārtika":
                count_query += " AND (category = 'Iepakotā pārtika' OR category = 'Bakaleja')"
            elif category_type == "Saldumi un uzkodas":
                count_query += " AND (category = 'Saldumi un uzkodas' OR (category = 'Bakaleja' and category2 = 'Saldumi'))"
            elif category_type == "Dzērieni":
                count_query += " AND (category = 'Dzērieni' AND category2 NOT IN ('Alus, sidri un kokteiļi', 'Vīni', 'Stiprie alkoholiskie dzērieni'))"
            elif category_type == "Alkoholiskie dzērieni":
                count_query += " AND (category2 IN ('Alkoholiskie dzērieni', 'Stiprie alkoholiskie dzērieni', 'Alus, sidri un kokteiļi'))"
            elif category_type == "Vīns":
                count_query += " AND (category2 IN ('Vīna dārzs', 'Karstvīns un karstie dzērieni', 'Vīni'))"
            elif category_type == "Skaistumkopšanai un higiēnai":
                count_query += " AND (category IN ('Skaistumkopšanai un higiēnai', 'Kosmētika un higiēna'))"
            elif category_type == "Zīdaiņiem un bērniem":
                count_query += " AND (category IN ('Zīdaiņiem un bērniem', 'Zīdaiņu un bērnu preces'))"
            elif category_type == "Sadzīves ķīmija":
                count_query += " AND (category = 'Sadzīves ķīmija' OR (category = 'Viss tīrīšanai un mājdzīvniekiem' AND category2 != 'Mājdzīvnieku preces'))"
            elif category_type == "Mājdzīvniekiem":
                count_query += " AND (category = 'Mājdzīvniekiem' OR (category = 'Viss tīrīšanai un mājdzīvniekiem' AND category2 = 'Mājdzīvnieku preces'))"
            elif category_type == "Mājai":
                count_query += " AND category IN ('Mājai, dārzam un atpūtai', 'Mājai un atpūtai')"
            elif category_type == "Pakalpojumi":
                count_query += " AND category2 = 'Pakalpojumi'"
            elif category_type == "Atlaide":
                count_query += " AND (discount_price IS NOT NULL OR old_price > price)"
            elif category_type == "Rimi":
                count_query += " AND store_id = 1"
            elif category_type == "Barbora":
                count_query += " AND store_id = 2"
            elif category_type:
                count_query += " AND category = %s"
                count_params.append(category_type)

        if filters:
            #Handle filters for stores with OR condition in count query
            store_filters = [f for f in filters if f in ["Rimi", "Barbora"]]
            other_filters = [f for f in filters if f not in ["Rimi", "Barbora"]]
            
            if store_filters:
                store_ids = []
                if "Rimi" in store_filters:
                    store_ids.append(1)
                if "Barbora" in store_filters:
                    store_ids.append(2)
                if store_ids:
                    store_conditions = " OR ".join([f"store_id = {id}" for id in store_ids])
                    count_query += f" AND ({store_conditions})"
            
            for filter_type in other_filters:
                if filter_type == "Atlaide":
                    count_query += " AND (discount_price IS NOT NULL OR old_price > price)"
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        #Transform products into a list of dictionaries for easier usage
        product_list = [
            {
                'id': row[0],
                'name': row[1],
                'price': row[2],
                'discount_price': row[3],
                'image': row[4],
                'category': row[5],
                'url': row[6],
                'store_id': row[7],
                'lowest_price': row[8],
                'discount_percentage': row[9]
            }
            for row in products
        ]

        return product_list, total_count

    except Exception as e:
        print(f"Error fetching products: {e}")
        return [], 0

#Route to display home page
@app.route('/')
def index():
    """Homepage route that lists products."""
    search_query = request.args.get('search')
    category_type = request.args.get('category')
    filters = request.args.getlist('filter')
    order_by = request.args.get('order')

    #Page parameters
    page = int(request.args.get('page', 1))
    per_page = 40

    products, total_count = fetch_products(search_query, category_type, filters, order_by, page, per_page)

    #Calculate total pages for display
    total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)

    #Render HTML and pass data
    return render_template(
        'index.html', 
        products=products, 
        search_query=search_query or "",
        category_type=category_type or "",
        filters=filters or [],
        order_by=order_by or "",
        page=page, 
        total_pages=total_pages
    )

#Route to fetch product price history for a specific product and timeframe
@app.route('/api/product/<int:product_id>/price_history/<timeframe>')
def get_price_history(product_id, timeframe):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        #date limits to create timeframe
        date_limit = {
            'week': 'CURRENT_DATE - INTERVAL \'7 days\'',
            'month': 'CURRENT_DATE - INTERVAL \'30 days\'',
            'year': 'CURRENT_DATE - INTERVAL \'365 days\'',
            'lifetime': 'CURRENT_DATE - INTERVAL \'100 years\''
        }.get(timeframe, 'CURRENT_DATE - INTERVAL \'30 days\'')

        #Query to get price history within the given time frame
        query = f"""
            WITH daily_prices AS (
                SELECT 
                    DATE(write_date) as date,
                    price,
                    ROW_NUMBER() OVER (PARTITION BY DATE(write_date) ORDER BY write_date DESC) as rn
                FROM product_history
                WHERE product_id = %s 
                AND write_date >= {date_limit}
                AND is_active = TRUE
                AND price IS NOT NULL
            )
            SELECT date, price
            FROM daily_prices
            WHERE rn = 1
            ORDER BY date;
        """
        
        cursor.execute(query, (product_id,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()

        #Prepare data to be returned as JSON
        data = [
            {
                'date': row[0].strftime('%Y-%m-%d'),
                'price': float(row[1])
            }
            for row in results
        ]

        return jsonify(data)

    except Exception as e:
        print(f"Error fetching price history: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
