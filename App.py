import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template, request
import networkx as nx
import numpy as np
import json

def parse_json_graph(data: str):
    try:
        parsed = json.loads(data)
        if 'elements' not in parsed:
            return None, None, None
        elements = parsed['elements']
        nodes = elements.get('nodes', [])
        edges = elements.get('edges', [])
        directed = parsed.get('directed')
        edges_list = []
        node_labels = {}
        for node in nodes:
            node_id = node['data']['id']
            label = node['data'].get('label', node_id)
            node_labels[node_id] = label
        for edge in edges:
            s = edge['data']['source']
            t = edge['data']['target']
            w = edge['data'].get('weight', 1.0)
            edges_list.append((s, t, w))
        return directed, edges_list, node_labels
    except:
        return None, None, None

def parse_edges_text(data: str):
    lines = [l.strip() for l in (data or "").splitlines() if l.strip()]

    has_new = any(l.startswith("#edge ") or l.startswith("#directed=") or l.startswith("#node ")
                  for l in lines)

    directed_from_file = None
    edges = []
    node_labels = {}

    if has_new:
        for l in lines:
            if l.startswith("#directed="):
                v = l[len("#directed="):].strip().lower()
                directed_from_file = v in ("1", "true", "yes")
            elif l.startswith("#node "):
                parts = l.split()
                if len(parts) >= 3:
                    node_id = parts[1]
                    if len(parts) >= 6:
                        label = parts[5]
                    else:
                        label = node_id
                    node_labels[node_id] = label
            elif l.startswith("#edge "):
                parts = l.split()
                if len(parts) >= 4:
                    s = parts[1]
                    t = parts[2]
                    try:
                        w = float(parts[3])
                    except ValueError:
                        w = 1.0
                    edges.append((s, t, w))
        return directed_from_file, edges, node_labels

    # старый формат
    for l in lines:
        parts = l.split()
        if len(parts) < 2:
            continue
        s, t = parts[0], parts[1]
        w = 1.0
        if len(parts) >= 3:
            try:
                w = float(parts[2])
            except ValueError:
                w = 1.0
        edges.append((s, t, w))

    return directed_from_file, edges, {}

def parse_graph_data(data: str):
    directed, edges, labels = parse_json_graph(data)
    if directed is not None:
        return directed, edges, labels
    return parse_edges_text(data)

def populate_graph(graph, edges_list, node_labels):
    id_to_label = {}
    for node_id, label in node_labels.items():
        id_to_label[node_id] = label
        graph.add_node(label, label=label)

    for s, t, w in edges_list:
        name_s = id_to_label.get(s, s)
        name_t = id_to_label.get(t, t)
        
        if name_s not in graph.nodes:
            graph.add_node(name_s, label=name_s)
        if name_t not in graph.nodes:
            graph.add_node(name_t, label=name_t)

        if w != 1:
            graph.add_edge(name_s, name_t, weight=w)
        else:
            graph.add_edge(name_s, name_t)

def create_graph_from_request(request, is_multi=False):
    data = request.form.get('graph_data', '')
    graph_type = request.form.get('graph_type', 'undirected')
    input_type = request.form.get('input_type', 'edges')

    print(f"DEBUG: Form graph_type = {graph_type}")

    directed_from_file, edges, node_labels = parse_graph_data(data)

    print(f"DEBUG: File directed = {directed_from_file}")

    if directed_from_file is not None:
        graph_type = 'directed' if directed_from_file else 'undirected'
        print(f"DEBUG: Overridden by file to = {graph_type}")

    if is_multi:
        if graph_type == 'directed':
            graph = nx.MultiDiGraph()
        else:
            graph = nx.MultiGraph()
    else:
        if graph_type == 'directed':
            graph = nx.DiGraph()
        else:
            graph = nx.Graph()

    if input_type == 'edges':
        populate_graph(graph, edges, node_labels)

    return graph, graph_type, input_type, data

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

def convert_graph_to_cytoscape_format(graph, graph_type, is_multi=False):
    nodes_list = []
    for node in graph.nodes():
        label = graph.nodes[node].get('label', str(node))
        nodes_list.append({
            'id': str(node),
            'label': label
        })
    
    edges_list = []
    edge_counter = 0
    if is_multi:
        for u, v, key in graph.edges(keys=True):
            edge_data = {
                'id': f"e{edge_counter}",
                'source': str(u),
                'target': str(v)
            }
            if graph.has_edge(u, v, key):
                edge_attrs = graph.get_edge_data(u, v, key)
                if edge_attrs and 'weight' in edge_attrs:
                    weight = edge_attrs['weight']
                    if weight != 0 and weight != 1:
                        edge_data['weight'] = float(weight)
            edges_list.append(edge_data)
            edge_counter += 1
    else:
        for u, v in graph.edges():
            edge_data = {
                'id': f"e{edge_counter}",
                'source': str(u),
                'target': str(v)
            }
            if graph.has_edge(u, v):
                edge_attrs = graph.get_edge_data(u, v)
                if edge_attrs and 'weight' in edge_attrs:
                    weight = edge_attrs['weight']
                    if weight != 0 and weight != 1:
                        edge_data['weight'] = float(weight)
            edges_list.append(edge_data)
            edge_counter += 1

    return nodes_list, edges_list

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/build_graph')
def build_graph():
    return render_template('build_graph.html')

@app.route('/build_adjacency_matrix')
def build_adjacency_matrix():
    return render_template('build_adjacency_matrix.html')

@app.route('/build_incidence_matrix')
def build_incidence_matrix():
    return render_template('build_incidence_matrix.html')

@app.route('/build_q_paths_matrix')
def build_q_paths_matrix():
    return render_template('build_q_paths_matrix.html')

@app.route('/build_multigraph')
def build_multigraph():
    return render_template('build_multigraph.html')

@app.route('/build_adj_matrix_multi')
def build_adj_matrix_multi():
    return render_template('build_adj_matrix_multi.html')

@app.route('/build_inc_matrix_multi')
def build_inc_matrix_multi():
    return render_template('build_inc_matrix_multi.html')

@app.route('/build_q_paths_matrix_multi')
def build_q_paths_matrix_multi():
    return render_template('build_q_paths_matrix_multi.html')

@app.route('/build_path_matrix')
def build_path_matrix():
    return render_template('build_path_matrix.html')

@app.route('/build_kirchhoff_matrix')
def build_kirchhoff_matrix():
    return render_template('build_kirchhoff_matrix.html')

@app.route('/build_kirchhoff_matrix_multi')
def build_kirchhoff_matrix_multi():
    return render_template('build_kirchhoff_matrix_multi.html')

@app.route('/draw_graph', methods=['POST'])
def draw_graph():
    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=False)

    if input_type == 'adjacency_matrix':
        try:
            lines = [line.strip() for line in data.strip().splitlines() if line.strip()]
            if not lines:
                return "Матрица смежности пуста."

            first_line_parts = lines[0].split()
            if not all(part.replace('.', '').replace('-', '').isdigit() for part in first_line_parts):
                headers = first_line_parts
                matrix_lines = lines[1:]
            else:
                n = len(first_line_parts)
                headers = [str(i) for i in range(n)]
                matrix_lines = lines

            matrix = []
            for line in matrix_lines:
                row = list(map(float, line.split()))
                if len(row) != len(headers):
                    return f"Строка '{line}' имеет неверное количество столбцов (ожидается {len(headers)})"
                matrix.append(row)

            if len(matrix) != len(headers):
                return "Количество строк матрицы не совпадает с количеством столбцов."

            graph_class = nx.DiGraph if graph_type == 'directed' else nx.Graph
            graph = graph_class()

            for h in headers:
                graph.add_node(h)

            for i, u in enumerate(headers):
                for j, v in enumerate(headers):
                    val = matrix[i][j]
                    if val != 0:
                        graph.add_edge(u, v, weight=val)

        except Exception as e:
            return f"Ошибка при обработке матрицы смежности: {e}"

    elif input_type == 'incidence_matrix':
        try:
            lines = [line.strip() for line in data.strip().splitlines() if line.strip()]
            if not lines:
                return "Матрица инцидентности пуста."

            first_line_parts = lines[0].split()
            if not all(part.replace('.', '').replace('-', '').isdigit() for part in first_line_parts):
                vertex_names = first_line_parts
                matrix_lines = lines[1:]
            else:
                vertex_names = [str(i) for i in range(len(first_line_parts))]
                matrix_lines = lines

            matrix = []
            for line in matrix_lines:
                row = list(map(float, line.split()))
                matrix.append(row)

            num_vertices = len(vertex_names)
            num_edges = len(matrix[0]) if matrix else 0
            if len(matrix) != num_vertices:
                return "Количество строк матрицы не соответствует количеству вершин."

            if graph_type == 'directed':
                allowed = {-1, 0, 1, 2}
            else:
                allowed = {0, 1, 2}
            values = set(val for row in matrix for val in row)
            if not values.issubset(allowed):
                return f"Матрица содержит недопустимые значения. Допустимы: {allowed}"

            graph_class = nx.DiGraph if graph_type == 'directed' else nx.Graph
            graph = graph_class()

            for name in vertex_names:
                graph.add_node(name)

            for j in range(num_edges):
                if graph_type == 'directed':
                    source = None
                    target = None
                    for i in range(num_vertices):
                        val = matrix[i][j]
                        if val == -1:
                            source = vertex_names[i]
                        elif val == 1:
                            target = vertex_names[i]
                        elif val == 2:
                            graph.add_edge(vertex_names[i], vertex_names[i])
                    if source is not None and target is not None:
                        graph.add_edge(source, target)
                else: 
                    nodes_in_edge = []
                    for i in range(num_vertices):
                        if matrix[i][j] != 0:
                            nodes_in_edge.append(vertex_names[i])
                    if len(nodes_in_edge) == 2:
                        u, v = nodes_in_edge
                        graph.add_edge(u, v)
                    elif len(nodes_in_edge) == 1:
                        u = nodes_in_edge[0]
                        graph.add_edge(u, u)

        except Exception as e:
            return f"Ошибка при обработке матрицы инцидентности: {e}"

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)
    
    return render_template('result_graph.html',
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           is_multi=False)

@app.route('/draw_adj', methods=['POST'])
def draw_adj_graph():
    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=False)

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    n = len(graph.nodes)
    nodes = list(graph.nodes())

    adjacency_matrix = np.zeros((n, n), dtype=float)

    for i in range(n):
        for j in range(n):
            if graph.has_edge(nodes[i], nodes[j]):
                weight = graph[nodes[i]][nodes[j]].get('weight', 1)
                adjacency_matrix[i][j] = weight

    adjacency_matrix_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(
        f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        adjacency_matrix_html += '<tr>'
        adjacency_matrix_html += f'<th>{node}</th>'
        for j in range(n):
            adjacency_matrix_html += f'<td>{adjacency_matrix[i][j]:g}</td>'
        adjacency_matrix_html += '</tr>'

    adjacency_matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)
    
    return render_template('result_adj.html',
                           adjacency_matrix=adjacency_matrix_html,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           is_multi=False,
                           matrix_type='adj')

@app.route('/draw_inc', methods=['POST'])
def draw_inc_graph():
    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=False)

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    incidence_matrix = nx.incidence_matrix(graph).toarray()
    edges = list(graph.edges(data=True))
    nodes = list(graph.nodes)

    incidence_matrix_html = '<table class="table table-bordered table-striped"><thead><tr><th>Узлы</th>' + ''.join(
        f'<th>{edge[0]} &rarr; {edge[1]}</th>' for edge in edges) + '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        incidence_matrix_html += '<tr>'
        incidence_matrix_html += f'<th>{node}</th>'
        for j in range(len(edges)):
            edge_data = edges[j][-1] 
            w = edge_data.get('weight', 1)

            if graph_type == 'directed':
                u, v = edges[j][0], edges[j][1] 
                if u == node and v == node:
                    value = 2 * w
                elif u == node:
                    value = -w
                elif v == node:
                    value = w
                else:
                    value = 0
            else:
                value = incidence_matrix[i][j]
            
            incidence_matrix_html += f'<td>{value:g}</td>'
        incidence_matrix_html += '</tr>'

    incidence_matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)
    
    return render_template('result_inc.html',
                           incidence_matrix=incidence_matrix_html,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           is_multi=False,
                           matrix_type='inc')

@app.route('/draw_q_paths_matrix', methods=['POST'])
def draw_q_paths_matrix():
    k = int(request.form['path_criteria'])

    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=False)

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    n = len(graph.nodes)
    nodes = list(graph.nodes())

    adjacency_matrix = np.zeros((n, n), dtype=float)

    for i in range(n):
        for j in range(n):
            if graph.has_edge(nodes[i], nodes[j]):
                adjacency_matrix[i][j] = 1

    q_paths_matrix = np.linalg.matrix_power(adjacency_matrix, k)

    q_paths_matrix_html = '<table class="table table-bordered table-striped"><thead><tr><th>Узлы</th>'
    for node in nodes:
        q_paths_matrix_html += f'<th>{node}</th>'
    q_paths_matrix_html += '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        q_paths_matrix_html += '<tr>'
        q_paths_matrix_html += f'<th>{node}</th>'
        for j in range(n):
            q_paths_matrix_html += f'<td>{int(q_paths_matrix[i][j])}</td>'
        q_paths_matrix_html += '</tr>'

    q_paths_matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)
    
    return render_template('result_q_paths.html',
                           q_paths_matrix=q_paths_matrix_html,
                           k=k,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           is_multi=False,
                           matrix_type='q_paths')

@app.route('/draw_multigraph', methods=['POST'])
def draw_multigraph():
    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=True)

    if input_type == 'adjacency_matrix':
        try:
            lines = [line.strip() for line in data.strip().splitlines() if line.strip()]
            if not lines:
                return "Матрица смежности пуста."

            first_line_parts = lines[0].split()
            if not all(part.replace('.', '').replace('-', '').isdigit() for part in first_line_parts):
                headers = first_line_parts
                matrix_lines = lines[1:] 
            else:
                n = len(first_line_parts)
                headers = [str(i) for i in range(n)]
                matrix_lines = lines

            matrix = []
            for line in matrix_lines:
                row = list(map(float, line.split()))
                if len(row) != len(headers):
                    return f"Строка '{line}' имеет неверное количество столбцов (ожидается {len(headers)})"
                matrix.append(row)

            if len(matrix) != len(headers):
                return "Количество строк матрицы не совпадает с количеством столбцов."

            graph_class = nx.DiGraph if graph_type == 'directed' else nx.Graph
            graph = graph_class()

            for h in headers:
                graph.add_node(h)

            for i, u in enumerate(headers):
                for j, v in enumerate(headers):
                    val = matrix[i][j]
                    if val != 0:
                        graph.add_edge(u, v, weight=val)

        except Exception as e:
            return f"Ошибка при обработке матрицы смежности: {e}"

    elif input_type == 'incidence_matrix':
        try:
            lines = [line.strip() for line in data.strip().splitlines() if line.strip()]
            if not lines:
                return "Матрица инцидентности пуста."

            first_line_parts = lines[0].split()
            if not all(part.replace('.', '').replace('-', '').isdigit() for part in first_line_parts):
                vertex_names = first_line_parts
                matrix_lines = lines[1:]
            else:
                vertex_names = [str(i) for i in range(len(first_line_parts))]
                matrix_lines = lines

            matrix = []
            for line in matrix_lines:
                row = list(map(float, line.split()))
                matrix.append(row)

            num_vertices = len(vertex_names)
            num_edges = len(matrix[0]) if matrix else 0
            if len(matrix) != num_vertices:
                return "Количество строк матрицы не соответствует количеству вершин."

            if graph_type == 'directed':
                allowed = {-1, 0, 1, 2}
            else:
                allowed = {0, 1, 2}
            values = set(val for row in matrix for val in row)
            if not values.issubset(allowed):
                return f"Матрица содержит недопустимые значения. Допустимы: {allowed}"

            graph_class = nx.DiGraph if graph_type == 'directed' else nx.Graph
            graph = graph_class()

            for name in vertex_names:
                graph.add_node(name)

            for j in range(num_edges):
                if graph_type == 'directed':
                    source = None
                    target = None
                    for i in range(num_vertices):
                        val = matrix[i][j]
                        if val == -1:
                            source = vertex_names[i]
                        elif val == 1:
                            target = vertex_names[i]
                        elif val == 2:
                            graph.add_edge(vertex_names[i], vertex_names[i])
                    if source is not None and target is not None:
                        graph.add_edge(source, target)
                else:
                    nodes_in_edge = []
                    for i in range(num_vertices):
                        if matrix[i][j] != 0:
                            nodes_in_edge.append(vertex_names[i])
                    if len(nodes_in_edge) == 2:
                        u, v = nodes_in_edge
                        graph.add_edge(u, v)
                    elif len(nodes_in_edge) == 1:
                        u = nodes_in_edge[0]
                        graph.add_edge(u, u)

        except Exception as e:
            return f"Ошибка при обработке матрицы инцидентности: {e}"

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."
    
    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(
        graph, graph_type, is_multi=True
    )

    return render_template('result_multigraph.html',
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type)

@app.route('/draw_adj_multi', methods=['POST'])
def draw_adj_multigraph():
    data = request.form['graph_data']
    graph_type = request.form['graph_type']
    input_type = request.form['input_type']

    if graph_type == 'directed':
        graph = nx.MultiDiGraph()
    else:
        graph = nx.MultiGraph()

    if input_type == 'edges':
        directed_from_file, edges, node_labels = parse_graph_data(data)

        if directed_from_file is not None:
            graph_type = 'directed' if directed_from_file else 'undirected'
            graph = nx.MultiDiGraph() if graph_type == 'directed' else nx.MultiGraph()

        for s, t, w in edges:
            graph.add_edge(s, t, weight=w)

        for node_id, label in node_labels.items():
            if node_id in graph.nodes:
                graph.nodes[node_id]['label'] = label

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    n = len(graph.nodes)
    nodes = list(graph.nodes())
    
    adj_matrix_multi = np.zeros((n, n), dtype=int)
    
    for i in range(n):
        for j in range(n):
            adj_matrix_multi[i][j] = graph.number_of_edges(nodes[i], nodes[j])
    
    adj_matrix_multi_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(
        f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'
    
    for i, node in enumerate(nodes):
        adj_matrix_multi_html += '<tr>'
        adj_matrix_multi_html += f'<th>{node}</th>'
        for j in range(n):
            adj_matrix_multi_html += f'<td>{adj_matrix_multi[i][j]}</td>'
        adj_matrix_multi_html += '</tr>'
    
    adj_matrix_multi_html += '</tbody></table>'
    
    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(
        graph, graph_type, is_multi=True
    )
    
    return render_template('result_adj_multi.html',
                           adj_matrix_multi=adj_matrix_multi_html,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           matrix_type='adj')

@app.route('/draw_inc_multi', methods=['POST'])
def draw_inc_multigraph():
    data = request.form.get('graph_data', '')
    graph_type = request.form.get('graph_type', 'undirected')
    
    directed_from_file, edges_parsed, node_labels = parse_graph_data(data)

    if directed_from_file is not None:
        graph_type = 'directed' if directed_from_file else 'undirected'

    if graph_type == 'directed':
        G = nx.MultiDiGraph()
    else:
        G = nx.MultiGraph()

    populate_graph(G, edges_parsed, node_labels)
    graph = G

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    nodes = list(graph.nodes())
    edges_list = list(graph.edges(keys=True, data=True)) 
    
    num_nodes = len(nodes)
    num_edges = len(edges_list)
    
    inc_matrix = np.zeros((num_nodes, num_edges), dtype=float)
    node_to_index = {node: i for i, node in enumerate(nodes)}

    for j, (u, v, key, data_attr) in enumerate(edges_list):
        w = data_attr.get('weight', 1.0)
        
        u_idx = node_to_index[u]
        v_idx = node_to_index[v]

        if graph_type == 'directed':
            if u == v:
                inc_matrix[u_idx][j] = 2 * w
            else:
                inc_matrix[u_idx][j] = -w
                inc_matrix[v_idx][j] = w
        else:
            if u == v:
                inc_matrix[u_idx][j] = 2 * w
            else:
                inc_matrix[u_idx][j] = w
                inc_matrix[v_idx][j] = w

    inc_matrix_multi_html = '<table class="table table-bordered table-striped"><thead><tr><th>Узлы</th>'
    for j, (u, v, key, data_attr) in enumerate(edges_list):
        w = data_attr.get('weight', 1.0)
        arrow = "→" if graph_type == 'directed' else "-"
        inc_matrix_multi_html += f'<th>e{j+1}: {u}{arrow}{v} (w:{w:g})</th>'
    inc_matrix_multi_html += '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        inc_matrix_multi_html += '<tr>'
        inc_matrix_multi_html += f'<th>{node}</th>'
        for j in range(num_edges):
            value = inc_matrix[i][j]
            inc_matrix_multi_html += f'<td>{value:g}</td>'
        inc_matrix_multi_html += '</tr>'
    inc_matrix_multi_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type, is_multi=True)

    return render_template('result_inc_multi.html',
                           inc_matrix_multi=inc_matrix_multi_html,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           matrix_type='inc')

@app.route('/draw_q_paths_matrix_multi', methods=['POST'])
def draw_q_paths_matrix_multi():
    k = int(request.form['path_criteria'])

    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=True)

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    n = len(graph.nodes)
    nodes = list(graph.nodes())
    
    adj_matrix_multi = np.zeros((n, n), dtype=int)
    
    for i in range(n):
        for j in range(n):
            adj_matrix_multi[i][j] = graph.number_of_edges(nodes[i], nodes[j])
    
    q_paths_matrix_multi = np.linalg.matrix_power(adj_matrix_multi, k)
    
    q_paths_matrix_multi_html = '<table class="table table-bordered table-striped"><thead><tr><th>Узлы</th>'
    for node in nodes:
        q_paths_matrix_multi_html += f'<th>{node}</th>'
    q_paths_matrix_multi_html += '</tr></thead><tbody>'
    
    for i, node in enumerate(nodes):
        q_paths_matrix_multi_html += '<tr>'
        q_paths_matrix_multi_html += f'<th>{node}</th>'
        for j in range(n):
            q_paths_matrix_multi_html += f'<td>{int(q_paths_matrix_multi[i][j])}</td>'
        q_paths_matrix_multi_html += '</tr>'
    
    q_paths_matrix_multi_html += '</tbody></table>'
    
    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(
        graph, graph_type, is_multi=True
    )
    
    return render_template('result_q_paths_matrix_multi.html',
                           q_paths_matrix_multi=q_paths_matrix_multi_html,
                           k=k,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           matrix_type='q_paths')

@app.route('/draw_path_matrix', methods=['POST'])
def draw_path_matrix():
    k = int(request.form['path_criteria'])

    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=False)

    n = len(graph.nodes)
    nodes = list(graph.nodes())

    path_matrix = [[set() for _ in range(n)] for _ in range(n)]

    for u, v in graph.edges():
        path_matrix[nodes.index(u)][nodes.index(v)].add((u, v))
        if not graph.is_directed():
            path_matrix[nodes.index(v)][nodes.index(u)].add((v, u))

    temp_matrix = path_matrix

    for _ in range(k - 1):
        new_matrix = [[set() for _ in range(n)] for _ in range(n)]

        for i in range(n):
            for j in range(n):
                for m in range(n):
                    if temp_matrix[i][m] and path_matrix[m][j]:
                        for first_path in temp_matrix[i][m]:
                            for second_path in path_matrix[m][j]:
                                new_path = first_path + second_path[1:]
                                new_matrix[i][j].add(new_path)

        temp_matrix = new_matrix

    path_matrix_html = '<table class="table table-bordered table-striped"><thead><tr><th>Узлы</th>'
    for node in nodes:
        path_matrix_html += f'<th>{node}</th>'
    path_matrix_html += '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        path_matrix_html += '<tr>'
        path_matrix_html += f'<th>{node}</th>'
        for j in range(n):
            path_matrix_html += f'<td>{list(temp_matrix[i][j])}</td>'
        path_matrix_html += '</tr>'

    path_matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)
    
    return render_template('result_path_matrix.html',
                           path_matrix=path_matrix_html,
                           k=k,
                           nodes=nodes_for_cytoscape,
                           edges=edges_for_cytoscape,
                           graph_type=graph_type,
                           is_multi=False,
                           matrix_type='paths')

@app.route('/interactive_graph')
def interactive_graph():
    return render_template("interactive_graph.html")

@app.route('/draw_kirchhoff_matrix', methods=['POST'])
def draw_kirchhoff_matrix():
    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=False)

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    nodes = list(graph.nodes())
    n = len(nodes)

    if graph_type == 'directed':
        nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)

        return render_template(
            'result_kirchhoff.html',
            kirchhoff_matrix='<p class="text-danger font-weight-bold">Граф ориентированный, матрицу Кирхгофа построить невозможно.</p>',
            nodes=nodes_for_cytoscape,
            edges=edges_for_cytoscape,
            graph_type=graph_type,
            is_multi=False,
            matrix_type='kirch'
        )

    adjacency_matrix = np.zeros((n, n), dtype=int)
    degree_matrix = np.zeros((n, n), dtype=int)

    for i in range(n):
        degree_matrix[i][i] = graph.degree(nodes[i])

    for i in range(n):
        for j in range(n):
            if i != j and graph.has_edge(nodes[i], nodes[j]):
                adjacency_matrix[i][j] = 1

    kirchhoff_matrix = degree_matrix - adjacency_matrix

    kirchhoff_matrix_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(
        f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        kirchhoff_matrix_html += '<tr>'
        kirchhoff_matrix_html += f'<th>{node}</th>'
        for j in range(n):
            kirchhoff_matrix_html += f'<td>{int(kirchhoff_matrix[i][j])}</td>'
        kirchhoff_matrix_html += '</tr>'

    kirchhoff_matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)

    return render_template(
        'result_kirchhoff.html',
        kirchhoff_matrix=kirchhoff_matrix_html,
        nodes=nodes_for_cytoscape,
        edges=edges_for_cytoscape,
        graph_type=graph_type,
        is_multi=False,
        matrix_type='kirch'
    )

@app.route('/draw_kirchhoff_matrix_multi', methods=['POST'])
def draw_kirchhoff_multigraph():
    graph, graph_type, input_type, data = create_graph_from_request(request, is_multi=True)

    if len(graph.nodes) == 0:
        return "Граф не содержит узлов."

    nodes = list(graph.nodes())
    n = len(nodes)

    if graph_type == 'directed':
        nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)

        return render_template(
            'result_kirchhoff.html',
            kirchhoff_matrix='<p class="text-danger font-weight-bold">Мультиграф ориентированный, матрицу Кирхгофа построить невозможно.</p>',
            nodes=nodes_for_cytoscape,
            edges=edges_for_cytoscape,
            graph_type=graph_type,
            is_multi=True,
            matrix_type='kirch'
        )

    adjacency_matrix = np.zeros((n, n), dtype=int)
    degree_matrix = np.zeros((n, n), dtype=int)

    for i in range(n):
        degree_matrix[i][i] = graph.degree(nodes[i])

    for i in range(n):
        for j in range(n):
            if i != j:
                adjacency_matrix[i][j] = graph.number_of_edges(nodes[i], nodes[j])

    kirchhoff_matrix = degree_matrix - adjacency_matrix

    kirchhoff_matrix_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(
        f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'

    for i, node in enumerate(nodes):
        kirchhoff_matrix_html += '<tr>'
        kirchhoff_matrix_html += f'<th>{node}</th>'
        for j in range(n):
            kirchhoff_matrix_html += f'<td>{int(kirchhoff_matrix[i][j])}</td>'
        kirchhoff_matrix_html += '</tr>'

    kirchhoff_matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(graph, graph_type)

    return render_template(
        'result_kirchhoff.html',
        kirchhoff_matrix=kirchhoff_matrix_html,
        nodes=nodes_for_cytoscape,
        edges=edges_for_cytoscape,
        graph_type=graph_type,
        is_multi=True,
        matrix_type='kirch'
    )

def compute_floyd_warshall(G, nodes):
    dist = {n: {m: float('inf') for m in nodes} for n in nodes}
    nxt = {n: {m: None for m in nodes} for n in nodes}
    
    for n in nodes:
        dist[n][n] = 0
        
    for u, v, data in G.edges(data=True):
        w = float(data.get('weight', 1))
        if w < dist[u][v]:
            dist[u][v] = w
            nxt[u][v] = v
        if not G.is_directed():
            if w < dist[v][u]:
                dist[v][u] = w
                nxt[v][u] = u
                
    for k in nodes:
        for i in nodes:
            for j in nodes:
                if dist[i][j] > dist[i][k] + dist[k][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
                    nxt[i][j] = nxt[i][k]
    return dist, nxt

@app.route('/build_weight_matrix')
def build_weight_matrix():
    return render_template('build_weight_matrix.html')

@app.route('/build_weight_matrix_multi')
def build_weight_matrix_multi():
    return render_template('build_weight_matrix_multi.html')

@app.route('/build_floyd_matrix')
def build_floyd_matrix():
    return render_template('build_floyd_matrix.html')

@app.route('/build_floyd_matrix_multi')
def build_floyd_matrix_multi():
    return render_template('build_floyd_matrix_multi.html')

@app.route('/draw_weight', methods=['POST'])
def draw_weight():
    G, graph_type, input_type, data = create_graph_from_request(request)

    requested_type = request.form.get('graph_type', 'undirected')
    if requested_type == 'undirected' and G.is_directed():
        G = G.to_undirected()
        graph_type = 'undirected'
        
    data = request.form.get('graph_data', '')
    graph_type = request.form.get('graph_type', 'undirected')
    
    directed_from_file, edges_list, node_labels = parse_graph_data(data)

    if directed_from_file is not None:
        graph_type = 'directed' if directed_from_file else 'undirected'

    if graph_type == 'directed':
        G = nx.DiGraph()
    else:
        G = nx.Graph()

    populate_graph(G, edges_list, node_labels)

    if len(G.nodes) == 0:
        return "Граф не содержит узлов."

    nodes = sorted(list(G.nodes()), key=lambda x: str(x))

    matrix_html = '<table class="table table-bordered"><thead><tr><th></th>'
    matrix_html += ''.join(f'<th>{node}</th>' for node in nodes)
    matrix_html += '</tr></thead><tbody>'

    for u in nodes:
        matrix_html += f'<tr><th>{u}</th>'
        for v in nodes:
            if u == v:
                val = 0
            elif G.has_edge(u, v):
                val = G[u][v].get('weight', 1)
            else:
                val = '∞'
            matrix_html += f'<td>{val}</td>'
        matrix_html += '</tr>'
    matrix_html += '</tbody></table>'

    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(
        G, graph_type, is_multi=False
    )

    return render_template(
        'result_weight.html',
        weight_matrix=matrix_html,
        nodes=nodes_for_cytoscape,
        edges=edges_for_cytoscape,
        graph_type=graph_type,
        is_multi=False,
        matrix_type='weight'
    )


@app.route('/draw_floyd', methods=['POST'])
def draw_floyd():
    data = request.form.get('graph_data')
    graph_type = request.form.get('graph_type', 'undirected')
    _, edges_list, node_labels = parse_graph_data(data)
    
    is_directed = (graph_type == 'directed')
    G = nx.DiGraph() if is_directed else nx.Graph()
    populate_graph(G, edges_list, node_labels)
    
    nodes = sorted(G.nodes())
    dist, nxt = compute_floyd_warshall(G, nodes)
    
    matrix_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'
    for u in nodes:
        matrix_html += f'<tr><th>{u}</th>'
        for v in nodes:
            d = dist[u][v]
            if d == float('inf'): val = '∞'
            elif u == v: val = '0'
            else: val = f"{d} ({nxt[u][v]})"
            matrix_html += f'<td>{val}</td>'
        matrix_html += '</tr>'
    matrix_html += '</tbody></table>'
    
    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(G, graph_type, is_multi=False)
    
    return render_template('result_floyd.html', 
                           floyd_matrix=matrix_html, 
                           nodes=nodes_for_cytoscape, 
                           edges=edges_for_cytoscape, 
                           graph_type=graph_type,
                           is_multi=False,
                           matrix_type='floyd')

@app.route('/draw_weight_multi', methods=['POST'])
def draw_weight_multi():
    data = request.form.get('graph_data')
    graph_type = request.form.get('graph_type', 'undirected')
    _, edges_list, node_labels = parse_graph_data(data)
    
    is_directed = (graph_type == 'directed')
    G = nx.MultiDiGraph() if is_directed else nx.MultiGraph()
    
    populate_graph(G, edges_list, node_labels)
    
    nodes = sorted(G.nodes())
    
    matrix_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'
    for u in nodes:
        matrix_html += f'<tr><th>{u}</th>'
        for v in nodes:
            if u == v:
                val = 0
            elif G.has_edge(u, v):
                all_data = G.get_edge_data(u, v)
                val = min(d.get('weight', 1) for d in all_data.values())
            else:
                val = '∞'
            matrix_html += f'<td>{val}</td>'
        matrix_html += '</tr>'
    matrix_html += '</tbody></table>'
    
    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(G, graph_type, is_multi=True)
    
    return render_template('result_weight_multi.html', 
                           weight_matrix=matrix_html, 
                           nodes=nodes_for_cytoscape, 
                           edges=edges_for_cytoscape, 
                           graph_type=graph_type,
                           is_multi=True,
                           matrix_type='weight')

@app.route('/draw_floyd_multi', methods=['POST'])
def draw_floyd_multi():
    data = request.form.get('graph_data')
    graph_type = request.form.get('graph_type', 'undirected')
    _, edges_list, node_labels = parse_graph_data(data)
    
    is_directed = (graph_type == 'directed')
    G_simple = nx.DiGraph() if is_directed else nx.Graph()
    G_render = nx.MultiDiGraph() if is_directed else nx.MultiGraph()
    
    id_to_label = {}
    for node_id, label in node_labels.items():
        id_to_label[node_id] = label
        G_simple.add_node(label, label=label)
        G_render.add_node(label, label=label)

    for s, t, w in edges_list:
        name_s = id_to_label.get(s, s)
        name_t = id_to_label.get(t, t)
        
        if name_s not in G_simple.nodes:
            G_simple.add_node(name_s, label=name_s)
            G_render.add_node(name_s, label=name_s)
        if name_t not in G_simple.nodes:
            G_simple.add_node(name_t, label=name_t)
            G_render.add_node(name_t, label=name_t)

        if G_simple.has_edge(name_s, name_t):
            if w < G_simple[name_s][name_t]['weight']:
                G_simple[name_s][name_t]['weight'] = w
        else:
            G_simple.add_edge(name_s, name_t, weight=w)
        
        G_render.add_edge(name_s, name_t, weight=w)
            
    nodes = sorted(list(G_simple.nodes()), key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
    dist, nxt = compute_floyd_warshall(G_simple, nodes)
    
    matrix_html = '<table class="table table-bordered"><thead><tr><th></th>' + ''.join(f'<th>{node}</th>' for node in nodes) + '</tr></thead><tbody>'
    for u in nodes:
        matrix_html += f'<tr><th>{u}</th>'
        for v in nodes:
            d = dist[u][v]
            if d == float('inf'): val = '∞'
            elif u == v: val = '0'
            else: val = f"{d} ({nxt[u][v]})"
            matrix_html += f'<td>{val}</td>'
        matrix_html += '</tr>'
    matrix_html += '</tbody></table>'
    
    nodes_for_cytoscape, edges_for_cytoscape = convert_graph_to_cytoscape_format(G_render, graph_type, is_multi=True)
    
    return render_template('result_floyd_multi.html', 
                           floyd_matrix=matrix_html, 
                           nodes=nodes_for_cytoscape, 
                           edges=edges_for_cytoscape, 
                           graph_type=graph_type,
                           is_multi=True,
                           matrix_type='floyd')

if __name__ == '__main__':
    app.run(debug=True)