// react-plotly.js's default export ("import Plot from 'react-plotly.js'")
// pulls in the full plotly.js bundle as an implicit peer dependency, which
// is large. We instead use the documented "factory" pattern with the
// explicit, smaller plotly.js-dist-min bundle we depend on directly in
// package.json -- same component API, smaller build output.
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

const Plot = createPlotlyComponent(Plotly);

export default Plot;
