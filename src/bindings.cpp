#include "index.hpp"
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
namespace py = pybind11;
using Array = py::array_t<float, py::array::c_style | py::array::forcecast>;
PYBIND11_MODULE(atlas_native, m) {
  m.def("kernel", &atlas::kernel);
  py::class_<atlas::Index>(m, "Index")
      .def(
          py::init([](Array data, std::vector<int32_t> tags, uint32_t degree,
                      uint32_t construction, uint32_t clusters, uint32_t seed) {
            if (data.ndim() != 2)
              throw std::invalid_argument("matrix required");
            std::vector<float> copy(data.data(), data.data() + data.size());
            auto d = size_t(data.shape(1));
            py::gil_scoped_release unlock;
            return atlas::Index(std::move(copy), d, std::move(tags), degree,
                                construction, clusters, seed);
          }),
          py::arg("data"), py::arg("tags"), py::arg("degree") = 12,
          py::arg("construction") = 80, py::arg("clusters") = 32,
          py::arg("seed") = 42)
      .def("search", &atlas::Index::search, py::arg("query"), py::arg("k") = 10,
           py::arg("effort") = 64, py::arg("algorithm") = "hnsw",
           py::arg("tag") = -1, py::call_guard<py::gil_scoped_release>())
      .def("save", &atlas::Index::save,
           py::call_guard<py::gil_scoped_release>())
      .def_static("load", &atlas::Index::load,
                  py::call_guard<py::gil_scoped_release>())
      .def_property_readonly("size", &atlas::Index::size)
      .def_property_readonly("dimensions", &atlas::Index::dimensions)
      .def_property_readonly("allocated_bytes", &atlas::Index::allocated_bytes)
      .def_property_readonly("clusters", &atlas::Index::clusters);
}
