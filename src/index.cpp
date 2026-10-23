#include "index.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <limits>
#include <numeric>
#include <queue>
#include <random>
#include <stdexcept>
#if defined(__aarch64__)
#include <arm_neon.h>
#elif defined(__SSE2__)
#include <emmintrin.h>
#endif
namespace atlas {
float scalar_l2(const float *a, const float *b, size_t d) {
  float s = 0;
  for (size_t i = 0; i < d; ++i) {
    const float x = a[i] - b[i];
    s += x * x;
  }
  return s;
}
float l2(const float *a, const float *b, size_t d) {
  size_t i = 0;
  float s = 0;
#if defined(__aarch64__)
  float32x4_t sum = vdupq_n_f32(0);
  for (; i + 4 <= d; i += 4) {
    const auto x = vsubq_f32(vld1q_f32(a + i), vld1q_f32(b + i));
    sum = vaddq_f32(sum, vmulq_f32(x, x));
  }
  s = vaddvq_f32(sum);
#elif defined(__SSE2__)
  __m128 sum = _mm_setzero_ps();
  for (; i + 4 <= d; i += 4) {
    const auto x = _mm_sub_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i));
    sum = _mm_add_ps(sum, _mm_mul_ps(x, x));
  }
  float lanes[4];
  _mm_storeu_ps(lanes, sum);
  for (float x : lanes)
    s += x;
#endif
  for (; i < d; ++i) {
    const float x = a[i] - b[i];
    s += x * x;
  }
  return s;
}
const char *kernel() {
#if defined(__aarch64__)
  return "NEON float32x4";
#elif defined(__SSE2__)
  return "SSE2 float32x4";
#else
  return "scalar";
#endif
}
float Index::distance(uint32_t id, const float *q) const {
  return l2(q, data_.data() + size_t(id) * d_, d_);
}
uint32_t Index::greedy(const float *q, uint32_t start, int level) const {
  auto best = Hit{distance(start, q), start};
  bool changed = true;
  while (changed) {
    changed = false;
    for (auto n : graph_[best.second][level]) {
      Hit h{distance(n, q), n};
      if (h < best) {
        best = h;
        changed = true;
      }
    }
  }
  return best.second;
}
std::vector<Hit> Index::layer(const float *q, uint32_t start, uint32_t ef,
                              int level) const {
  // Per-thread scratch has no shared writes; epoch wrap clears all marks.
  thread_local std::vector<uint32_t> marks;
  thread_local uint32_t epoch = 0;
  if (marks.size() < size())
    marks.resize(size(), 0);
  if (++epoch == 0) {
    std::fill(marks.begin(), marks.end(), 0);
    epoch = 1;
  }
  std::priority_queue<Hit, std::vector<Hit>, std::greater<Hit>> pending;
  std::priority_queue<Hit> found;
  Hit first{distance(start, q), start};
  pending.push(first);
  found.push(first);
  marks[start] = epoch;
  while (!pending.empty()) {
    auto h = pending.top();
    pending.pop();
    if (found.size() >= ef && h > found.top())
      break;
    for (auto n : graph_[h.second][level]) {
      if (marks[n] == epoch)
        continue;
      marks[n] = epoch;
      Hit next{distance(n, q), n};
      if (found.size() < ef || next < found.top()) {
        pending.push(next);
        found.push(next);
        if (found.size() > ef)
          found.pop();
      }
    }
  }
  std::vector<Hit> result;
  while (!found.empty()) {
    result.push_back(found.top());
    found.pop();
  }
  std::sort(result.begin(), result.end());
  return result;
}
std::vector<uint32_t> Index::select(std::vector<Hit> candidates,
                                    uint32_t limit) const {
  std::sort(candidates.begin(), candidates.end());
  std::vector<uint32_t> selected;
  for (auto [dist, id] : candidates) {
    bool good = true;
    for (auto other : selected)
      if (distance(other, data_.data() + size_t(id) * d_) < dist) {
        good = false;
        break;
      }
    if (good)
      selected.push_back(id);
    if (selected.size() == limit)
      break;
  }
  return selected;
}
Index::Index(std::vector<float> data, size_t dimensions,
             std::vector<int32_t> tags, uint32_t m, uint32_t construction,
             uint32_t clusters, uint32_t seed)
    : d_(dimensions), m_(m), construction_(construction), clusters_(clusters),
      data_(std::move(data)), tags_(std::move(tags)) {
  if (d_ == 0 || d_ > 4096 || tags_.empty() || tags_.size() > 10000000 ||
      data_.size() / d_ != size() || data_.size() % d_ || m_ < 2 || m_ > 64 ||
      construction_ < m_ || construction_ > 4096 || clusters_ < 1 ||
      clusters_ > size() || clusters_ > 4096)
    throw std::invalid_argument("invalid index shape or build parameters");
  for (float v : data_)
    if (!std::isfinite(v) || std::abs(v) > 1e10f)
      throw std::invalid_argument("invalid vector value");
  for (auto t : tags_)
    if (t < 0)
      throw std::invalid_argument("negative tag");
  std::mt19937 rng(seed);
  graph_.reserve(size());
  for (uint32_t id = 0; id < size(); ++id) {
    const double u = (double(rng()) + 1) / (double(std::mt19937::max()) + 2);
    int level = std::min(16, int(-std::log(u) / std::log(double(m_))));
    graph_.emplace_back(size_t(level) + 1);
    if (id == 0) {
      entry_ = 0;
      max_level_ = level;
      continue;
    }
    const float *q = data_.data() + size_t(id) * d_;
    uint32_t current = entry_;
    for (int l = max_level_; l > level; --l)
      current = greedy(q, current, l);
    for (int l = std::min(level, max_level_); l >= 0; --l) {
      auto candidates = layer(q, current, construction_, l);
      current = candidates.front().second;
      auto neighbors = select(candidates, m_);
      graph_[id][l] = neighbors;
      for (auto n : neighbors) {
        auto &links = graph_[n][l];
        links.push_back(id);
        const uint32_t cap = l == 0 ? 2 * m_ : m_;
        if (links.size() > cap) {
          std::vector<Hit> scored;
          for (auto x : links)
            scored.emplace_back(distance(x, data_.data() + size_t(n) * d_), x);
          links = select(std::move(scored), cap);
        }
      }
    }
    if (level > max_level_) {
      entry_ = id;
      max_level_ = level;
    }
  }
  train_ivf();
}
void Index::train_ivf() {
  // Deterministic bounded training sample; assign every base vector after
  // training.
  const size_t count = std::min(size(), size_t(10000));
  centers_.resize(size_t(clusters_) * d_);
  for (uint32_t c = 0; c < clusters_; ++c)
    std::copy_n(data_.data() + (size_t(c) * size() / clusters_) * d_, d_,
                centers_.data() + size_t(c) * d_);
  for (int iteration = 0; iteration < 8; ++iteration) {
    std::vector<double> sums(centers_.size());
    std::vector<size_t> counts(clusters_);
    for (size_t j = 0; j < count; ++j) {
      size_t i = j * size() / count;
      uint32_t best = 0;
      float dist = std::numeric_limits<float>::infinity();
      for (uint32_t c = 0; c < clusters_; ++c) {
        auto ds =
            l2(data_.data() + i * d_, centers_.data() + size_t(c) * d_, d_);
        if (ds < dist) {
          dist = ds;
          best = c;
        }
      }
      ++counts[best];
      for (size_t k = 0; k < d_; ++k)
        sums[size_t(best) * d_ + k] += data_[i * d_ + k];
    }
    for (uint32_t c = 0; c < clusters_; ++c)
      if (counts[c])
        for (size_t k = 0; k < d_; ++k)
          centers_[size_t(c) * d_ + k] =
              float(sums[size_t(c) * d_ + k] / counts[c]);
  }
  lists_.resize(clusters_);
  for (uint32_t i = 0; i < size(); ++i) {
    uint32_t best = 0;
    float dist = std::numeric_limits<float>::infinity();
    for (uint32_t c = 0; c < clusters_; ++c) {
      auto ds = l2(data_.data() + size_t(i) * d_,
                   centers_.data() + size_t(c) * d_, d_);
      if (ds < dist) {
        dist = ds;
        best = c;
      }
    }
    lists_[best].push_back(i);
  }
}
std::vector<Hit> Index::search(const std::vector<float> &q, uint32_t k,
                               uint32_t effort, const std::string &algorithm,
                               int32_t tag) const {
  if (q.size() != d_ || k == 0 || k > size() || effort == 0 ||
      effort > 10000000 || tag < -1)
    throw std::invalid_argument("invalid query parameters");
  for (float v : q)
    if (!std::isfinite(v) || std::abs(v) > 1e10f)
      throw std::invalid_argument("invalid query value");
  std::vector<Hit> candidates;
  if (algorithm == "hnsw" && tag < 0) {
    uint32_t current = entry_;
    for (int l = max_level_; l > 0; --l)
      current = greedy(q.data(), current, l);
    candidates = layer(q.data(), current, std::max(k, effort), 0);
  } else if (algorithm == "exact" || (algorithm == "hnsw" && tag >= 0)) {
    // Selective filters use exact eligible scan; never disconnect traversal or
    // silently underfill.
    std::priority_queue<Hit> heap;
    for (uint32_t i = 0; i < size(); ++i)
      if (tag < 0 || tags_[i] == tag) {
        Hit h{distance(i, q.data()), i};
        if (heap.size() < k)
          heap.push(h);
        else if (h < heap.top()) {
          heap.pop();
          heap.push(h);
        }
      }
    while (!heap.empty()) {
      candidates.push_back(heap.top());
      heap.pop();
    }
  } else if (algorithm == "ivf") {
    std::vector<Hit> coarse;
    for (uint32_t c = 0; c < clusters_; ++c)
      coarse.emplace_back(l2(q.data(), centers_.data() + size_t(c) * d_, d_),
                          c);
    std::sort(coarse.begin(), coarse.end());
    std::priority_queue<Hit> heap;
    for (uint32_t c = 0; c < std::min(effort, clusters_); ++c)
      for (auto i : lists_[coarse[c].second])
        if (tag < 0 || tags_[i] == tag) {
          Hit h{distance(i, q.data()), i};
          if (heap.size() < k)
            heap.push(h);
          else if (h < heap.top()) {
            heap.pop();
            heap.push(h);
          }
        }
    while (!heap.empty()) {
      candidates.push_back(heap.top());
      heap.pop();
    }
  } else
    throw std::invalid_argument("unknown algorithm");
  std::sort(candidates.begin(), candidates.end());
  if (candidates.size() > k)
    candidates.resize(k);
  return candidates;
}
size_t Index::allocated_bytes() const {
  size_t bytes = sizeof(*this) + data_.capacity() * sizeof(float) +
                 centers_.capacity() * sizeof(float) +
                 tags_.capacity() * sizeof(int32_t) +
                 graph_.capacity() * sizeof(graph_[0]) +
                 lists_.capacity() * sizeof(lists_[0]);
  for (const auto &levels : graph_) {
    bytes += levels.capacity() * sizeof(levels[0]);
    for (const auto &links : levels)
      bytes += links.capacity() * sizeof(uint32_t);
  }
  for (const auto &list : lists_)
    bytes += list.capacity() * sizeof(uint32_t);
  return bytes;
}
// Portable little-endian words and FNV-1a accidental-corruption checksum, not
// authentication.
namespace {
uint64_t checksum(const std::vector<uint32_t> &v) {
  uint64_t h = 14695981039346656037ULL;
  for (auto x : v)
    for (int b = 0; b < 4; ++b) {
      h ^= (x >> (8 * b)) & 255;
      h *= 1099511628211ULL;
    }
  return h;
}
} // namespace
void Index::save(const std::string &path) const {
  std::vector<uint32_t> w{0x41544c53,   1,      uint32_t(size()),
                          uint32_t(d_), m_,     construction_,
                          clusters_,    entry_, uint32_t(max_level_)};
  for (float f : data_) {
    uint32_t x;
    std::memcpy(&x, &f, 4);
    w.push_back(x);
  }
  for (auto t : tags_)
    w.push_back(uint32_t(t));
  for (const auto &levels : graph_) {
    w.push_back(uint32_t(levels.size()));
    for (const auto &links : levels) {
      w.push_back(uint32_t(links.size()));
      w.insert(w.end(), links.begin(), links.end());
    }
  }
  for (float f : centers_) {
    uint32_t x;
    std::memcpy(&x, &f, 4);
    w.push_back(x);
  }
  for (const auto &list : lists_) {
    w.push_back(uint32_t(list.size()));
    w.insert(w.end(), list.begin(), list.end());
  }
  auto h = checksum(w);
  w.push_back(uint32_t(h));
  w.push_back(uint32_t(h >> 32));
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  for (auto x : w)
    for (int b = 0; b < 4; ++b)
      out.put(char(x >> (8 * b)));
  if (!out)
    throw std::runtime_error("snapshot write failed");
  out.close();
  if (!out)
    throw std::runtime_error("snapshot close failed");
}
Index Index::load(const std::string &path) {
  std::ifstream in(path, std::ios::binary | std::ios::ate);
  if (!in)
    throw std::runtime_error("snapshot open failed");
  auto length = in.tellg();
  if (length < 44 || length > std::streamoff(8ULL << 30) || length % 4)
    throw std::runtime_error("snapshot size invalid");
  in.seekg(0);
  std::vector<uint32_t> w(size_t(length) / 4);
  for (auto &x : w) {
    x = 0;
    for (int b = 0; b < 4; ++b) {
      int c = in.get();
      if (c < 0)
        throw std::runtime_error("snapshot truncated");
      x |= uint32_t(c) << (8 * b);
    }
  }
  uint64_t expected = w[w.size() - 2] | (uint64_t(w.back()) << 32);
  w.resize(w.size() - 2);
  if (checksum(w) != expected)
    throw std::runtime_error("snapshot checksum mismatch");
  size_t p = 0;
  auto take = [&]() {
    if (p >= w.size())
      throw std::runtime_error("snapshot truncated");
    return w[p++];
  };
  if (take() != 0x41544c53 || take() != 1)
    throw std::runtime_error("snapshot version invalid");
  Index x;
  uint32_t n = take();
  x.d_ = take();
  x.m_ = take();
  x.construction_ = take();
  x.clusters_ = take();
  x.entry_ = take();
  x.max_level_ = int(take());
  if (n == 0 || n > 10000000 || x.d_ == 0 || x.d_ > 4096 || x.m_ < 2 ||
      x.m_ > 64 || x.clusters_ < 1 || x.clusters_ > n || x.clusters_ > 4096 ||
      x.entry_ >= n || x.max_level_ < 0 || x.max_level_ > 16 ||
      size_t(n) * x.d_ > w.size())
    throw std::runtime_error("snapshot header invalid");
  auto number = [&]() {
    auto bits = take();
    float f;
    std::memcpy(&f, &bits, 4);
    if (!std::isfinite(f) || std::abs(f) > 1e10f)
      throw std::runtime_error("snapshot float invalid");
    return f;
  };
  x.data_.resize(size_t(n) * x.d_);
  for (auto &v : x.data_)
    v = number();
  x.tags_.resize(n);
  for (auto &t : x.tags_) {
    t = int32_t(take());
    if (t < 0)
      throw std::runtime_error("snapshot tag invalid");
  }
  x.graph_.resize(n);
  for (uint32_t i = 0; i < n; ++i) {
    auto levels = take();
    if (levels < 1 || levels > 17)
      throw std::runtime_error("snapshot level invalid");
    x.graph_[i].resize(levels);
    for (uint32_t l = 0; l < levels; ++l) {
      auto count = take();
      if (count > (l == 0 ? 2 * x.m_ : x.m_))
        throw std::runtime_error("snapshot degree invalid");
      auto &links = x.graph_[i][l];
      for (uint32_t j = 0; j < count; ++j) {
        auto id = take();
        if (id >= n || id == i ||
            std::find(links.begin(), links.end(), id) != links.end())
          throw std::runtime_error("snapshot edge invalid");
        links.push_back(id);
      }
    }
  }
  if (x.graph_[x.entry_].size() != size_t(x.max_level_ + 1))
    throw std::runtime_error("snapshot entry invalid");
  for (const auto &levels : x.graph_)
    for (size_t l = 0; l < levels.size(); ++l)
      for (auto id : levels[l])
        if (x.graph_[id].size() <= l)
          throw std::runtime_error("snapshot edge level invalid");
  x.centers_.resize(size_t(x.clusters_) * x.d_);
  for (auto &v : x.centers_)
    v = number();
  x.lists_.resize(x.clusters_);
  std::vector<bool> seen(n);
  size_t total = 0;
  for (auto &list : x.lists_) {
    auto count = take();
    if (count > n)
      throw std::runtime_error("snapshot list invalid");
    for (uint32_t j = 0; j < count; ++j) {
      auto id = take();
      if (id >= n || seen[id])
        throw std::runtime_error("snapshot assignment invalid");
      seen[id] = true;
      list.push_back(id);
      ++total;
    }
  }
  if (total != n || p != w.size())
    throw std::runtime_error("snapshot trailing or missing data");
  return x;
}
} // namespace atlas
