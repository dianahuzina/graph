function loadFileToTextarea(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();

    reader.onload = function (e) {
        const text = e.target.result.trim();
        const textarea = document.getElementById("graph_data");

        if (!textarea) return;

        try {
            const json = JSON.parse(text);

            if (json.elements && json.elements.edges) {
                let result = "";

                json.elements.edges.forEach(edge => {
                    const source = edge.data.source;
                    const target = edge.data.target;
                    const weight = edge.data.weight;

                    if (weight !== undefined) {
                        result += `${source} ${target} ${weight}\n`;
                    } else {
                        result += `${source} ${target}\n`;
                    }
                });

                textarea.value = result.trim();
                return;
            }
        } catch (e) {
            // не JSON
        }

        textarea.value = text;
    };

    reader.readAsText(file);
}
