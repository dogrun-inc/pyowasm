require "erb"
require "js"
require "json"
require "cgi"

TEMPLATE = <<~ERB
<!DOCTYPE html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>pyowasm Ruby.WASM Edition</title>
    <style>
      :root { color-scheme: dark; font-family: "Segoe UI", sans-serif; }
      body { margin: 0; background: #0f172a; color: #e2e8f0; }
      main { max-width: 1120px; margin: 0 auto; padding: 24px; }
      h1 { margin-bottom: 8px; }
      .panel { background: rgba(15, 23, 42, 0.92); border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
      textarea, input, button { font: inherit; }
      textarea { width: 100%; min-height: 120px; margin-top: 8px; padding: 10px; border-radius: 8px; border: 1px solid #475569; background: #020617; color: #f8fafc; }
      .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
      button { cursor: pointer; padding: 10px 16px; border: none; border-radius: 8px; background: #2563eb; color: white; }
      .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #1d4ed8; margin-right: 8px; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; }
      th, td { padding: 8px 10px; border-bottom: 1px solid #334155; text-align: left; }
      .status { color: #93c5fd; margin-top: 8px; }
      .warning { color: #fbbf24; }
      .muted { color: #94a3b8; }
    </style>
  </head>
  <body>
    <main>
      <h1>🧬 pyowasm Ruby.WASM Edition</h1>
      <p class="muted">RBH オーソログ解析を Ruby.WASM で実行するサンプルです。</p>
      <form id="analysis-form">
        <div class="panel">
          <div class="grid">
            <div>
              <label for="sample_a">Species A (FASTA / FAA)</label>
              <textarea id="sample_a" name="sample_a"><%= @sample_a %></textarea>
            </div>
            <div>
              <label for="sample_b">Species B (FASTA / FAA)</label>
              <textarea id="sample_b" name="sample_b"><%= @sample_b %></textarea>
            </div>
          </div>
          <div class="grid" style="margin-top: 12px;">
            <div>
              <label for="keywords_a">Species A キーワード</label>
              <input id="keywords_a" name="keywords_a" value="<%= @keywords_a %>" style="width: 100%; margin-top: 8px; padding: 8px; border-radius: 8px; border: 1px solid #475569; background: #020617; color: #f8fafc;" />
            </div>
            <div>
              <label for="keywords_b">Species B キーワード</label>
              <input id="keywords_b" name="keywords_b" value="<%= @keywords_b %>" style="width: 100%; margin-top: 8px; padding: 8px; border-radius: 8px; border: 1px solid #475569; background: #020617; color: #f8fafc;" />
            </div>
          </div>
          <div class="grid" style="margin-top: 12px;">
            <div>
              <label for="k">k-mer サイズ</label>
              <input id="k" name="k" type="number" min="3" max="6" value="<%= @k %>" style="width: 100%; margin-top: 8px; padding: 8px; border-radius: 8px; border: 1px solid #475569; background: #020617; color: #f8fafc;" />
            </div>
            <div>
              <label for="top_n">top_n</label>
              <input id="top_n" name="top_n" type="number" min="1" max="100" value="<%= @top_n %>" style="width: 100%; margin-top: 8px; padding: 8px; border-radius: 8px; border: 1px solid #475569; background: #020617; color: #f8fafc;" />
            </div>
          </div>
          <div style="margin-top: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <button id="runButton" type="button">🚀 解析を実行</button>
            <span class="status"><%= @status_message %></span>
          </div>
        </div>
      </form>
      <div class="panel">
        <h2>解析結果</h2>
        <div class="muted"><%= @summary_html %></div>
        <div class="warning"><%= @warnings_html %></div>
        <div><%= @results_html %></div>
      </div>
    </main>
  </body>
</html>
ERB

module OrthologRubyApp
  module_function

  DEFAULT_SAMPLE_A = ">gene_a1\nMKTQFQKESR\n"
  DEFAULT_SAMPLE_B = ">gene_b1\nMKTQFQKESR\n"

  def parse_fasta(sample_text)
    normalized = sample_text.to_s.gsub("\uFEFF", "").split("\n").map(&:rstrip).join("\n")
    records = []
    current_id = nil
    current_desc = ""
    current_sequence = []

    normalized.split("\n").each do |line|
      stripped = line.strip
      next if stripped.empty?

      if stripped.start_with?(">")
        if current_id
          records << { id: current_id, description: current_desc, sequence: current_sequence.join("").upcase }
        end

        header = stripped[1..].strip
        parts = header.split(" ", 2)
        current_id = parts[0]
        current_desc = parts[1] || ""
        current_sequence = []
      else
        current_sequence << stripped
      end
    end

    if current_id
      records << { id: current_id, description: current_desc, sequence: current_sequence.join("").upcase }
    end

    records
  end

  def normalize_keywords(keywords)
    return [] if keywords.nil?

    if keywords.is_a?(String)
      return keywords.split(",").map(&:strip).reject(&:empty?)
    end

    keywords.map(&:to_s).map(&:strip).reject(&:empty?)
  end

  def normalize_text(text)
    text.to_s.gsub("_", " ").gsub("-", " ").downcase.gsub(/\s+/, " ").strip
  end

  def filter_records(records, keywords)
    normalized_keywords = normalize_keywords(keywords)
    return records if normalized_keywords.empty?

    records.select do |record|
      haystack = normalize_text("#{record[:id]} #{record[:description]}")
      normalized_keywords.any? do |keyword|
        normalize_text(keyword).split.any? { |token| haystack.include?(token) }
      end
    end
  end

  def jaccard_similarity(seq_a, seq_b, k)
    return 0.0 if seq_a.nil? || seq_b.nil? || seq_a.empty? || seq_b.empty?

    kmers_a = (0..(seq_a.length - k)).map { |idx| seq_a[idx, k] }.to_set
    kmers_b = (0..(seq_b.length - k)).map { |idx| seq_b[idx, k] }.to_set
    return 0.0 if kmers_a.empty? || kmers_b.empty?

    union = kmers_a | kmers_b
    intersection = kmers_a & kmers_b
    intersection.length.to_f / union.length.to_f
  end

  def simple_alignment_identity(seq_a, seq_b)
    return 0.0 if seq_a.nil? || seq_b.nil? || seq_a.empty? || seq_b.empty?

    max_len = [seq_a.length, seq_b.length].max
    return 0.0 if max_len.zero?

    matches = seq_a.each_char.zip(seq_b.each_char).count { |left, right| left == right }
    (matches.to_f / max_len * 100.0).round(2)
  end

  def simple_alignment_score(seq_a, seq_b)
    return 0.0 if seq_a.nil? || seq_b.nil? || seq_a.empty? || seq_b.empty?

    seq_a.each_char.zip(seq_b.each_char).count { |left, right| left == right }.to_f
  end

  def build_result(sample_a, sample_b, keywords_a, keywords_b, k, top_n)
    require "set"

    warnings = []
    seqs_a = parse_fasta(sample_a)
    seqs_b = parse_fasta(sample_b)

    if seqs_a.empty? || seqs_b.empty?
      return { rows: [], warnings: warnings, summary: { count: 0, average_identity: 0.0, max_identity: 0.0 } }
    end

    seqs_a = filter_records(seqs_a, keywords_a)
    seqs_b = filter_records(seqs_b, keywords_b)

    warnings << "Species A のキーワード抽出を適用しました。" if keywords_a && !normalize_keywords(keywords_a).empty?
    warnings << "Species B のキーワード抽出を適用しました。" if keywords_b && !normalize_keywords(keywords_b).empty?

    if seqs_a.empty? || seqs_b.empty?
      return { rows: [], warnings: warnings, summary: { count: 0, average_identity: 0.0, max_identity: 0.0 } }
    end

    use_python_alignment = false
    begin
      require "pycall"
      align_module = PyCall.import_module("Bio.Align")
      pairwise_aligner = align_module.PairwiseAligner.new
      pairwise_aligner.substitution_matrix = align_module.substitution_matrices.load("BLOSUM62")
      pairwise_aligner.open_gap_score = -11
      pairwise_aligner.extend_gap_score = -1
      use_python_alignment = true
    rescue LoadError, NameError => error
      warnings << "Python bridge が利用できないため、Ruby の簡易アラインメントで解析しました。"
    end

    hits_a_to_b = {}
    seqs_a.each do |record_a|
      best_subject = nil
      best_score = -1.0
      seqs_b.each do |record_b|
        score = jaccard_similarity(record_a[:sequence], record_b[:sequence], k)
        if score > best_score
          best_score = score
          best_subject = record_b[:id]
        end
      end
      hits_a_to_b[record_a[:id]] = [best_subject, best_score] unless best_subject.nil?
    end

    hits_b_to_a = {}
    seqs_b.each do |record_b|
      best_subject = nil
      best_score = -1.0
      seqs_a.each do |record_a|
        score = jaccard_similarity(record_b[:sequence], record_a[:sequence], k)
        if score > best_score
          best_score = score
          best_subject = record_a[:id]
        end
      end
      hits_b_to_a[record_b[:id]] = [best_subject, best_score] unless best_subject.nil?
    end

    rows = []
    seqs_a.each do |record_a|
      reciprocal = hits_b_to_a[record_a[:id]]
      next unless reciprocal

      subject_id = hits_a_to_b[record_a[:id]]&.first
      next if subject_id.nil? || reciprocal.first != record_a[:id]

      seq_a = record_a[:sequence]
      seq_b = seqs_b.find { |record_b| record_b[:id] == subject_id }&.fetch(:sequence, "")
      next if seq_b.nil? || seq_b.empty?

      if use_python_alignment
        self_score_a = pairwise_aligner.score(seq_a, seq_a)
        alignment_score = pairwise_aligner.score(seq_a, seq_b)
        identity = self_score_a.positive? ? [alignment_score.to_f / self_score_a.to_f * 100.0, 100.0].min : 0.0
        bitscore = alignment_score.round(2)
      else
        identity = simple_alignment_identity(seq_a, seq_b)
        bitscore = simple_alignment_score(seq_a, seq_b).round(2)
      end

      rows << {
        query: record_a[:id],
        subject: subject_id,
        identity: identity.round(2),
        bitscore: bitscore,
      }
    end

    rows.sort_by! { |row| -row[:identity] }
    rows = rows.first(top_n.to_i)

    payload_rows = rows.map do |row|
      {
        "query" => row[:query],
        "subject" => row[:subject],
        "identity" => row[:identity],
        "bitscore" => row[:bitscore],
      }
    end
    identities = payload_rows.map { |row| row["identity"].to_f }

    {
      rows: payload_rows,
      warnings: warnings,
      summary: {
        count: payload_rows.length,
        average_identity: identities.empty? ? 0.0 : (identities.sum / identities.length).round(2),
        max_identity: identities.empty? ? 0.0 : identities.max.round(2),
      },
    }
  end

  def normalize_result(result)
    return result if result.is_a?(Hash)
    return JSON.parse(result) if result.is_a?(String)

    {}
  end

  def build_summary_html(result)
    return "まだ実行されていません。" if result.nil?

    result_hash = normalize_result(result)
    summary = result_hash["summary"] || result_hash[:summary] || {}
    count = summary["count"] || summary[:count] || 0
    average_identity = summary["average_identity"] || summary[:average_identity] || 0.0
    max_identity = summary["max_identity"] || summary[:max_identity] || 0.0

    "<span class=\"pill\">オーソログ数: #{count}</span>" \
      "<span class=\"pill\">平均一致率: #{average_identity.round(2)}%</span>" \
      "<span class=\"pill\">最高一致率: #{max_identity.round(2)}%</span>"
  end

  def build_warnings_html(result)
    result_hash = normalize_result(result)
    warnings = result_hash["warnings"] || result_hash[:warnings] || []
    return "" if warnings.empty?

    warnings.map { |warning| "<p class=\"warning\">#{warning}</p>" }.join
  end

  def build_results_html(result)
    result_hash = normalize_result(result)
    rows = result_hash["rows"] || result_hash[:rows] || []
    return "<p class=\"muted\">オーソログ候補が見つかりませんでした。</p>" if rows.empty?

    rows_html = rows.map do |row|
      query = row["query"] || row[:query]
      subject = row["subject"] || row[:subject]
      identity = row["identity"] || row[:identity]
      bitscore = row["bitscore"] || row[:bitscore]

      <<~HTML
        <tr>
          <td>#{ERB::Util.html_escape(query.to_s)}</td>
          <td>#{ERB::Util.html_escape(subject.to_s)}</td>
          <td>#{ERB::Util.html_escape(identity.to_s)}%</td>
          <td>#{ERB::Util.html_escape(bitscore.to_s)}</td>
        </tr>
      HTML
    end.join

    <<~HTML
      <table>
        <thead>
          <tr>
            <th>Query</th>
            <th>Subject</th>
            <th>Identity</th>
            <th>Bitscore</th>
          </tr>
        </thead>
        <tbody>#{rows_html}</tbody>
      </table>
    HTML
  end

  def render_page(sample_a: DEFAULT_SAMPLE_A, sample_b: DEFAULT_SAMPLE_B, keywords_a: "caffeine, methyltransferase", keywords_b: "caffeine, methyltransferase", k: 4, top_n: 20, result: nil, status_message: "初期化待機中…")
    @sample_a = sample_a
    @sample_b = sample_b
    @keywords_a = keywords_a
    @keywords_b = keywords_b
    @k = k
    @top_n = top_n
    @status_message = status_message
    @summary_html = build_summary_html(result)
    @warnings_html = build_warnings_html(result)
    @results_html = build_results_html(result)

    ERB.new(TEMPLATE).result(binding)
  end
end

# 画面表示
document = JS.global[:document]
html = OrthologRubyApp.render_page
document[:body][:innerHTML] = html

# イベント登録
document.getElementById("runButton").addEventListener("click") do |e|
  sample_a = document.getElementById("sample_a")[:value].to_s
  sample_b = document.getElementById("sample_b")[:value].to_s
  keywords_a = document.getElementById("keywords_a")[:value].to_s
  keywords_b = document.getElementById("keywords_b")[:value].to_s
  k = document.getElementById("k")[:value].to_i
  top_n = document.getElementById("top_n")[:value].to_i
  status = document.querySelector('.status')

  status[:textContent] = '解析中...'

  begin
    result = OrthologRubyApp.build_result(sample_a, sample_b, keywords_a, keywords_b, k, top_n)
    summary_html = OrthologRubyApp.build_summary_html(result)
    warnings_html = OrthologRubyApp.build_warnings_html(result)
    results_html = OrthologRubyApp.build_results_html(result)

    document.querySelector('.muted')[:innerHTML] = summary_html
    document.querySelector('.warning')[:innerHTML] = warnings_html
    document.querySelector('.panel:last-of-type div:last-of-type')[:innerHTML] = results_html
    status[:textContent] = '解析完了'
  rescue => error
    puts error.message
    status[:textContent] = '解析に失敗しました'
  end
end
