#pragma once
#include <cstdint>
#include <string>
#include <utility>
#include <vector>
namespace atlas {
using Hit = std::pair<float, uint32_t>;
float scalar_l2(const float *a, const float *b, size_t d);
float l2(const float *a, const float *b, size_t d);
const char *kernel();
class Index {
public:
  Index(std::vector<float> data, size_t dimensions, std::vector<int32_t> tags,
        uint32_t m = 12, uint32_t construction = 80, uint32_t clusters = 32,
        uint32_t seed = 42);
  std::vector<Hit> search(const std::vector<float> &query, uint32_t k,
                          uint32_t effort, const std::string &algorithm,
                          int32_t tag = -1) const;
  void save(const std::string &path) const;
  static Index load(const std::string &path);
  size_t size() const { return tags_.size(); }
  size_t dimensions() const { return d_; }
  size_t allocated_bytes() const;
  uint32_t clusters() const { return clusters_; }

private:
  Index() = default;
  size_t d_ = 0;
  uint32_t m_ = 0, construction_ = 0, clusters_ = 0, entry_ = 0;
  int max_level_ = -1;
  std::vector<float> data_, centers_;
  std::vector<int32_t> tags_;
  std::vector<std::vector<std::vector<uint32_t>>> graph_;
  std::vector<std::vector<uint32_t>> lists_;
  float distance(uint32_t id, const float *q) const;
  uint32_t greedy(const float *q, uint32_t start, int layer) const;
  std::vector<Hit> layer(const float *q, uint32_t start, uint32_t ef,
                         int level) const;
  std::vector<uint32_t> select(std::vector<Hit> candidates,
                               uint32_t limit) const;
  void train_ivf();
};
} // namespace atlas
