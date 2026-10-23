#include "index.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <thread>
void check(bool ok, const char *why) {
  if (!ok)
    throw std::runtime_error(why);
}
int main() {
  std::mt19937 rng(42);
  std::uniform_real_distribution<float> unif(-1, 1);
  size_t checks = 0;
  for (size_t d : {1, 3, 4, 7, 16, 33, 128}) {
    std::vector<float> a(d), b(d);
    for (int j = 0; j < 100; ++j) {
      for (auto &v : a)
        v = unif(rng);
      for (auto &v : b)
        v = unif(rng);
      auto s = atlas::scalar_l2(a.data(), b.data(), d);
      auto v = atlas::l2(a.data(), b.data(), d);
      check(std::abs(s - v) < 1e-4f * std::max(1.f, s), "SIMD parity");
      ++checks;
    }
  }
  const size_t n = 500, d = 17;
  std::vector<float> data(n * d);
  for (auto &v : data)
    v = unif(rng);
  std::vector<int32_t> tags(n);
  for (size_t i = 0; i < n; ++i)
    tags[i] = int32_t(i % 5);
  atlas::Index index(data, d, tags, 12, 80, 16);
  for (size_t i = 0; i < 50; ++i) {
    std::vector<float> q(data.begin() + i * d, data.begin() + (i + 1) * d);
    auto exact = index.search(q, 10, 1, "exact");
    auto ivf = index.search(q, 10, 16, "ivf");
    check(exact == ivf, "full probe exact");
    auto h = index.search(q, 10, 500, "hnsw");
    check(h == exact, "high effort reference");
    for (int32_t t = 0; t < 6; ++t) {
      auto filtered = index.search(q, 10, 1, "hnsw", t);
      check(filtered == index.search(q, 10, 1, "exact", t), "filter reference");
      for (auto hit : filtered)
        check(tags[hit.second] == t, "tag leak");
      ++checks;
    }
  }
  auto path = std::filesystem::temp_directory_path() /
              ("atlas-test-" + std::to_string(rng()) + ".bin");
  index.save(path.string());
  auto loaded = atlas::Index::load(path.string());
  std::vector<float> q(data.begin(), data.begin() + d);
  for (auto algo : {"hnsw", "ivf", "exact"})
    check(index.search(q, 10, 16, algo) == loaded.search(q, 10, 16, algo),
          "reload parity");
  std::atomic<bool> ok = true;
  std::vector<std::thread> threads;
  for (int t = 0; t < 8; ++t)
    threads.emplace_back([&]() {
      for (int j = 0; j < 200; ++j)
        if (index.search(q, 10, 64, "hnsw") != loaded.search(q, 10, 64, "hnsw"))
          ok = false;
    });
  for (auto &t : threads)
    t.join();
  check(ok, "concurrent readers");
  {
    std::fstream f(path, std::ios::binary | std::ios::in | std::ios::out);
    f.seekg(100);
    char c;
    f.get(c);
    f.seekp(100);
    f.put(char(c ^ 1));
  }
  bool rejected = false;
  try {
    auto bad = atlas::Index::load(path.string());
    (void)bad;
  } catch (const std::runtime_error &e) {
    rejected = true;
    std::cout << "caught corrupted snapshot: " << e.what() << '\n';
  }
  check(rejected, "corruption accepted");
  std::filesystem::remove(path);
  bool invalid = false;
  try {
    index.search({NAN}, 10, 1, "hnsw");
  } catch (const std::invalid_argument &) {
    invalid = true;
  }
  check(invalid, "invalid query accepted");
  std::cout << "PASS " << checks
            << " randomized kernel/filter checks; full-probe/exact/HNSW, "
               "persistence, 8 concurrent readers x 200 pairs; kernel="
            << atlas::kernel() << '\n';
}
