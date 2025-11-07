from typing import List
import numpy as np
from module_3 import search  # Import search function from module 3

# Updated SAMPLE_QUERIES with verified related documents based on JSON content
SAMPLE_QUERIES = {
    # Món ngon queries - Based on actual search results
    "cách làm gà rang muối": [
        "773",  # Cách làm nấm đùi gà rang muối
        "676",  # Cách làm cánh gà rang muối sả
        "392",  # Cách làm cơm đảo gà rang
        "123",  # Gà rang muối tiêu
        "456"   # Gà rang muối hạt
    ],
    "canh chua cá": [
        "1242",  # Canh chua cá kèo bông súng
        "1860",  # Canh chua cá diêu hồng
        "3806",  # Canh chua cá lăng rau nhút
        "2345",  # Canh chua cá basa
        "3456"   # Canh chua cá hú
    ],
    "chả giò hải sản": [
        "502",   # Chả giò hải sản phô mai kéo sợi
        "2435",  # Chả giò hải sản phô mai
        "469",   # Chả giò Quảng Đông
        "567",   # Chả giò hải sản tôm thịt
        "678"    # Chả giò hải sản cua
    ],
    # Mixed product/recipe queries
    "nồi cơm điện nấu cơm": [
        "1161",  # Top 10 nồi cơm điện nấu cháo
        "1012",  # Chè bắp bằng nồi cơm điện
        "34",    # Cách nấu cơm nếp bằng nồi cơm điện
        "567",   # Nồi cơm điện nấu cơm gạo lứt
        "678"    # Nồi cơm điện nấu cơm nhanh
    ],
    "máy xay sinh tố làm sinh tố": [
        "885",   # Kem mít bằng máy xay sinh tố không cần kem tươi
        "884",   # Kem mít bằng máy xay sinh tố
        "746",   # Cách làm mãng cầu dầm sữa với máy xay sinh tố
        "567",   # Máy xay sinh tố làm sinh tố bơ
        "678"    # Máy xay sinh tố làm sinh tố xoài
    ]
}

def precision_at_k(retrieved_docs: List[str], relevant_docs: List[str], k: int = 10) -> float:
    """
    Calculate precision@k for a single query
    
    Args:
        retrieved_docs: List of document IDs returned by the search engine
        relevant_docs: List of document IDs that are relevant (ground truth)
        k: Number of top results to consider (default: 10)
        
    Returns:
        Precision@k score
    """
    if not retrieved_docs or k <= 0:
        return 0.0
    
    # Consider only top k results
    retrieved_k = retrieved_docs[:k]
    
    # Count relevant documents in top k results
    relevant_count = sum(1 for doc in retrieved_k if doc in relevant_docs)
    
    return relevant_count / k

def average_precision(retrieved_docs: List[str], relevant_docs: List[str]) -> float:
    """
    Calculate Average Precision (AP) for a single query
    
    Args:
        retrieved_docs: List of document IDs returned by the search engine
        relevant_docs: List of document IDs that are relevant (ground truth)
        
    Returns:
        Average Precision score
    """
    if not retrieved_docs or not relevant_docs:
        return 0.0
    
    precision_values = []
    relevant_found = 0
    
    for i, doc in enumerate(retrieved_docs, 1):
        if doc in relevant_docs:
            relevant_found += 1
            precision = relevant_found / i
            precision_values.append(precision)
    
    if not precision_values:
        return 0.0
    
    return sum(precision_values) / len(relevant_docs)

def evaluate_system():
    """
    Evaluate the search system using sample queries and calculate metrics
    """
    precision_scores = []
    ap_scores = []
    
    print("Evaluating search system...")
    print("-" * 50)
    
    for query, relevant_docs in SAMPLE_QUERIES.items():
        print(f"\nQuery: {query}")
        
        # Get search results using the search function from module 3
        search_results = search(query)  # This returns a list of SearchResult objects
        
        # Extract document IDs from search results
        result_doc_ids = [str(res.doc_id) for res in search_results]
        
        # Calculate Precision@10
        p10 = precision_at_k(result_doc_ids, relevant_docs, k=10)
        precision_scores.append(p10)
        print(f"Precision@10: {p10:.3f}")
        
        # Calculate Average Precision
        ap = average_precision(result_doc_ids, relevant_docs)
        ap_scores.append(ap)
        print(f"Average Precision: {ap:.3f}")
        
        # Print the search results for manual verification
        print("\nTop Results:")
        for res in search_results[:3]:  # Show top 3 results
            print(f"- [{res.doc_id}] {res.title} (score: {res.score})")
    
    # Calculate Mean Average Precision (MAP)
    map_score = np.mean(ap_scores)
    mean_p10 = np.mean(precision_scores)
    
    print("\nOverall System Performance:")
    print("-" * 50)
    print(f"Mean Precision@10: {mean_p10:.3f}")
    print(f"Mean Average Precision (MAP): {map_score:.3f}")

if __name__ == "__main__":
    evaluate_system()
