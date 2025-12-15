#!/usr/bin/env python3
"""
compare_images_mathpix.py

Compare images from a GT folder to images produced by Mathpix (MP folder).
Outputs:
 - an HTML report (default: compare_report.html)
 - a CSV file compare_report.csv

Usage:
    python compare_images_mathpix.py /path/to/gt_folder /path/to/mathpix_folder --out report.html

Notes:
 - Recommended: install imagehash for pHash checks (pip install ImageHash).
 - Uses SIFT if available else ORB.
"""

import os
import sys
import cv2
import argparse
import numpy as np
from PIL import Image
import csv
import base64
import io
from datetime import datetime

# Try optional perceptual hashing
USE_PHASH = False
try:
    import imagehash
    USE_PHASH = True
except Exception:
    USE_PHASH = False

# ---------------------------
# Configurable thresholds
# ---------------------------
LOWE_RATIO = 0.75           # Lowe ratio for descriptor matching
MIN_GOOD_MATCHES = 8        # minimum good matches to try homography
MIN_INLIERS = 15            # minimum inliers to accept match
MIN_INLIER_RATIO = 0.5      # inliers / good matches ratio to accept match
PHASH_DIST_THRESHOLD = 12    # if phash distance below this, consider match strong (optional)
MAX_COMPARE = None          # set to int to limit comparisons for quick tests

# Thumbnail size for HTML report
THUMB_W = 300

# ---------------------------
# Utility functions
# ---------------------------
def list_images(folder):
    exts = {'.png','.jpg','.jpeg','.tiff','.bmp','.gif',' .webp'}
    files = []
    for fname in sorted(os.listdir(folder)):
        low = fname.lower()
        if any(low.endswith(ext) for ext in exts):
            files.append(os.path.join(folder, fname))
    return files

def load_image_cv(path):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        # fallback to PIL
        pil = Image.open(path).convert('RGB')
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img

def pil_to_data_uri(pil_image, fmt='PNG', max_width=None):
    """Return data URI for a PIL image; optionally resize to max_width (keeps aspect)."""
    img = pil_image.copy()
    if max_width and img.width > max_width:
        w = max_width
        h = int(img.height * (w / img.width))
        img = img.resize((w,h), Image.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format=fmt)
    img_str = base64.b64encode(buffered.getvalue()).decode('ascii')
    return f"data:image/{fmt.lower()};base64,{img_str}"

def cv_to_pil(img_cv):
    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img_rgb)

def compute_phash_pil(pil_img):
    if not USE_PHASH:
        return None
    return imagehash.phash(pil_img)

# Preprocessing: grayscale + resize to height H preserving aspect ratio
def preprocess_for_features(img_cv, height=600):
    h = img_cv.shape[0]
    if h == 0:
        return img_cv
    scale = height / float(h)
    new_w = int(img_cv.shape[1] * scale)
    resized = cv2.resize(img_cv, (new_w, height))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    # slight blur can help with scanned noise
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    return gray

# Initialize feature detector and matcher
def init_feature_detector():
    # Try SIFT (float descriptors)
    try:
        sift = cv2.SIFT_create()
        detector = sift
        descriptor_type = 'SIFT'
        # FLANN params for SIFT
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        matcher = cv2.FlannBasedMatcher(index_params, search_params)
        return detector, matcher, descriptor_type
    except Exception:
        # fallback to ORB (binary descriptors)
        orb = cv2.ORB_create(nfeatures=2000)
        detector = orb
        descriptor_type = 'ORB'
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        return detector, matcher, descriptor_type

def match_descriptors(matcher, des1, des2, descriptor_type):
    """Return list of good matches using kNN + Lowe ratio for float descriptors,
       or similar approach for binary (ORB) descriptors."""
    if des1 is None or des2 is None:
        return []
    try:
        if descriptor_type == 'ORB':
            # BFMatcher returns list of DMatch; use knnMatch with k=2 for ratio test
            knn = matcher.knnMatch(des1, des2, k=2)
        else:
            # FLANN expects float32
            if des1.dtype != np.float32:
                des1 = np.float32(des1)
            if des2.dtype != np.float32:
                des2 = np.float32(des2)
            knn = matcher.knnMatch(des1, des2, k=2)
    except Exception:
        # final fallback - brute force single matches
        try:
            single = matcher.match(des1, des2)
            knn = [[m] for m in single]
        except Exception:
            return []

    good = []
    for pair in knn:
        if len(pair) == 2:
            m, n = pair
            if m.distance < LOWE_RATIO * n.distance:
                good.append(m)
        else:
            # if we only have one match in pair - accept with looser check
            m = pair[0]
            good.append(m)
    return good

def compute_match_score(kp1, kp2, good_matches):
    """Compute homography with RANSAC and return inliers and mask (if possible)."""
    if len(good_matches) < MIN_GOOD_MATCHES:
        return {
            'inliers': 0,
            'inlier_mask': None,
            'homography': None
        }
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1,1,2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1,1,2)
    try:
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if mask is None:
            inliers = 0
        else:
            inliers = int(mask.sum())
        return {'inliers': inliers, 'inlier_mask': mask, 'homography': H}
    except Exception:
        return {'inliers': 0, 'inlier_mask': None, 'homography': None}


# ---------------------------
# Additional helper functions
# ---------------------------
import re

def parse_gt_name(path):
    """
    GT format: <book>_page_<page_number>_<image_index>.png
    Returns (page_number, image_index)
    """
    name = os.path.basename(path)
    m = re.search(r'_page_(\d+)_([0-9]+)', name)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))

def parse_mathpix_name(path):
    """
    Mathpix format examples:
       code-086.jpg          -> page 86, img_index = 0  (only image)
       code-086(1).jpg       -> page 86, img_index = 1
       code-086(2).jpg       -> page 86, img_index = 2
    Returns (page_number, image_index)
    """
    name = os.path.basename(path)
    
    # extract "086" or "86" before "("
    m = re.search(r'-(\d+)', name)
    if not m:
        return None, None
    page = int(m.group(1))

    # extract "(n)" index if exists
    idx = 0
    m2 = re.search(r'\((\d+)\)', name)
    if m2:
        idx = int(m2.group(1))  # starts at 1

    return page, idx


from collections import defaultdict

def group_by_page(image_list, parser_fn):
    pages = defaultdict(list)
    for img in image_list:
        page, idx = parser_fn(img)
        if page is not None:
            pages[page].append((idx, img))
    # sort by index within page
    for p in pages:
        pages[p].sort(key=lambda x: x[0])
    return pages


def find_closest_page(page, page_breaks, page_positions, book_len, is_forward=True):
    print(f"Finding closest page for page {page}, is_forward={is_forward}")
    print(f"Page breaks available: {page_breaks[:5] if len(page_breaks) > 5 else page_breaks}... (total: {len(page_breaks)})")
    
    if str(page) in page_breaks:
        print(f"Exact match found for page {page}")
        return page_positions[page]
    
    if is_forward:
        bound = book_len
        forward = page
        while forward <= bound:
            if str(forward) in page_breaks:
                print(f"Forward match found: {forward}")
                return page_positions[forward]
            forward += 1
        print(f"No forward match found for page {page}")
        return -1
    else:
        bound = 0
        backward = page
        while backward >= bound:
            if str(backward) in page_breaks:
                print(f"Backward match found: {backward}")
                return page_positions[backward]
            backward -= 1
        print(f"No backward match found for page {page}")
        return 0  # No valid page found



# ---------------------------
# Main comparison logic
# ---------------------------
# def compare_folders(gt_folder, mp_folder, html_out='compare_report.html', csv_out='compare_report.csv'):
    # gt_images = list_images(gt_folder)
    # mp_images = list_images(mp_folder)

    # # Group images by page
    # gt_pages = group_by_page(gt_images, parse_gt_name)
    # mp_pages = group_by_page(mp_images, parse_mathpix_name)

    # if len(gt_images) == 0:
    #     print("No GT images found in", gt_folder)
    #     return
    # if len(mp_images) == 0:
    #     print("No Mathpix images found in", mp_folder)
    #     return

    # detector, matcher, descriptor_type = init_feature_detector()
    # print(f"Using descriptor: {descriptor_type}")

    # # Precompute images, descriptors, keypoints, phash
    # mp_db = []
    # print("Preprocessing Mathpix images...")
    # for i, mp_path in enumerate(mp_images):
    #     if MAX_COMPARE and i >= MAX_COMPARE:
    #         break
    #     img_cv = load_image_cv(mp_path)
    #     proc = preprocess_for_features(img_cv)
    #     kp, des = detector.detectAndCompute(proc, None)
    #     pil = cv_to_pil(img_cv)
    #     ph = compute_phash_pil(pil) if USE_PHASH else None
    #     mp_db.append({'path': mp_path, 'cv': img_cv, 'proc': proc, 'kp': kp, 'des': des, 'phash': ph, 'pil': pil})

    # results = []
    # total_gt = sum(len(v) for v in gt_pages.values())
    # progress = 0
    # print("Comparing GT images (page-constrained)...")

    # for page in sorted(gt_pages.keys()):
    #     gt_list = gt_pages[page]
    #     mp_list = mp_pages.get(page, [])

    #      # If counts match → assume correct and skip
    #     if len(gt_list) == len(mp_list):
    #         for idx, gt_path in gt_list:
    #             results.append({
    #                 'gt_path': gt_path,
    #                 'gt_pil': cv_to_pil(load_image_cv(gt_path)),
    #                 'mp_path': None,
    #                 'mp_pil': None,
    #                 'inliers': 0,
    #                 'good_matches': 0,
    #                 'inlier_ratio': 0,
    #                 'phash_dist': None,
    #                 'accepted': True,
    #                 'reason': 'Count match → assumed correct'
    #             })
    #         continue

        # # Otherwise: perform local matching only within this page
        # print(f"Page {page}: GT={len(gt_list)}, MP={len(mp_list)} → comparing...")
        
        # # Precompute MP page descriptors
        # mp_db = []
        # for idx, mp_path in mp_list:
        #     img_cv = load_image_cv(mp_path)
        #     proc = preprocess_for_features(img_cv)
        #     kp, des = detector.detectAndCompute(proc, None)
        #     pil = cv_to_pil(img_cv)
        #     ph = compute_phash_pil(pil) if USE_PHASH else None
        #     mp_db.append({'path': mp_path, 'kp': kp, 'des': des, 'phash': ph, 'pil': pil})

        # # Compare each GT only to MP images in same page
        # for idx, gt_path in gt_list:
        #     progress += 1
        #     gt_cv = load_image_cv(gt_path)
        #     gt_proc = preprocess_for_features(gt_cv)
        #     kp1, des1 = detector.detectAndCompute(gt_proc, None)
        #     gt_pil = cv_to_pil(gt_cv)
        #     gt_ph = compute_phash_pil(gt_pil) if USE_PHASH else None

        #     best = {
        #         'mp_path': None, 'mp_pil': None,
            #     'inliers': 0, 'good_matches': 0,
            #     'inlier_ratio': 0, 'phash_dist': None
            # }

            # for mp in mp_db:
            #     good = match_descriptors(matcher, des1, mp['des'], descriptor_type)
            #     num_good = len(good)
            #     match_info = compute_match_score(kp1, mp['kp'], good)
            #     inliers = match_info['inliers']
            #     ratio = (inliers / num_good) if num_good else 0

            #     ph_dist = None
            #     if USE_PHASH and gt_ph and mp['phash']:
            #         ph_dist = gt_ph - mp['phash']

            #     # choose best
            #     better = (inliers > best['inliers']) or \
            #             (inliers == best['inliers'] and ratio > best['inlier_ratio'])

            #     if better:
            #         best.update({
            #             'mp_path': mp['path'],
            #             'mp_pil': mp['pil'],
            #             'inliers': inliers,
            #             'good_matches': num_good,
            #             'inlier_ratio': ratio,
            #             'phash_dist': ph_dist
            #         })
            # # Acceptance logic
            # accepted, reason = False, ""
            # if best['mp_path'] is None:
            #     accepted, reason = False, "No candidate images on this page"
            # elif best['inliers'] >= MIN_INLIERS and best['inlier_ratio'] >= MIN_INLIER_RATIO:
            #     accepted, reason = True, "Strong geometric match (SIFT+RANSAC)"
            # elif USE_PHASH and best['phash_dist'] is not None and best['phash_dist'] <= PHASH_DIST_THRESHOLD:
            #     accepted, reason = True, f"phash match ({best['phash_dist']})"
            # else:
            #     accepted, reason = False, "Nearest candidate does not meet thresholds"

            # results.append({
            #     'gt_path': gt_path,
            #     'gt_pil': gt_pil,
            #     'mp_path': best['mp_path'],
            #     'mp_pil': best['mp_pil'],
            #     'inliers': best['inliers'],
            #     'good_matches': best['good_matches'],
            #     'inlier_ratio': best['inlier_ratio'],
            #     'phash_dist': best['phash_dist'],
            #     'accepted': accepted,
            #     'reason': reason
            # })

            # print(f"[{progress}/{total_gt}] Page {page} GT:{os.path.basename(gt_path)} → "
            #   f"{os.path.basename(best['mp_path']) if best['mp_path'] else '---'} | "
            #   f"inliers={best['inliers']} accepted={accepted}")


  
    # # Write CSV
    # with open(csv_out, 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['gt_path','mp_path','inliers','good_matches','inlier_ratio','phash_dist','accepted','reason'])
    #     for r in results:
    #         writer.writerow([r['gt_path'], r['mp_path'] or '', r['inliers'], r['good_matches'], f"{r['inlier_ratio']:.3f}", r['phash_dist'] if r['phash_dist'] is not None else '', r['accepted'], r['reason']])

    # # Generate HTML report
    # generate_html_report(results, html_out)
    # print("Done. HTML report:", html_out, "CSV:", csv_out)


def compare_folders(gt_folder, mp_folder, html_out='compare_report.html', csv_out='compare_report.csv'):
    gt_images = list_images(gt_folder)
    mp_images = list_images(mp_folder)

    # Group images by page
    gt_pages = group_by_page(gt_images, parse_gt_name)
    mp_pages = group_by_page(mp_images, parse_mathpix_name)

    if len(gt_images) == 0:
        print("No GT images found in", gt_folder)
        return
    if len(mp_images) == 0:
        print("No Mathpix images found in", mp_folder)
        return

    detector, matcher, descriptor_type = init_feature_detector()
    print(f"Using descriptor: {descriptor_type}")

    # Precompute images, descriptors, keypoints, phash
    mp_db = []
    print("Preprocessing Mathpix images...")
    for i, mp_path in enumerate(mp_images):
        if MAX_COMPARE and i >= MAX_COMPARE:
            break
        img_cv = load_image_cv(mp_path)
        proc = preprocess_for_features(img_cv)
        kp, des = detector.detectAndCompute(proc, None)
        pil = cv_to_pil(img_cv)
        ph = compute_phash_pil(pil) if USE_PHASH else None
        mp_db.append({'path': mp_path, 'cv': img_cv, 'proc': proc, 'kp': kp, 'des': des, 'phash': ph, 'pil': pil})

    results = []
    total_gt = sum(len(v) for v in gt_pages.values())
    progress = 0
    print("Comparing GT images (page-constrained)...")

    for page in sorted(gt_pages.keys()):
        gt_list = gt_pages[page]
        mp_list = mp_pages.get(page, [])

         # If counts match → assume correct and skip
        # if len(gt_list) == len(mp_list):
        #     for idx, gt_path in gt_list:
        #         results.append({
        #             'gt_path': gt_path,
        #             'gt_pil': cv_to_pil(load_image_cv(gt_path)),
        #             'mp_path': None,
        #             'mp_pil': None,
        #             'inliers': 0,
        #             'good_matches': 0,
        #             'inlier_ratio': 0,
        #             'phash_dist': None,
        #             'accepted': True,
        #             'reason': 'Count match → assumed correct'
        #         })
        #     continue

        # Otherwise: perform local matching only within this page
        print(f"Page {page}: GT={len(gt_list)}, MP={len(mp_list)} → comparing...")
        
        # Precompute MP page descriptors
        mp_db = []
        for idx, mp_path in mp_list:
            img_cv = load_image_cv(mp_path)
            proc = preprocess_for_features(img_cv)
            kp, des = detector.detectAndCompute(proc, None)
            pil = cv_to_pil(img_cv)
            ph = compute_phash_pil(pil) if USE_PHASH else None
            mp_db.append({'idx':idx, 'path': mp_path, 'kp': kp, 'des': des, 'phash': ph, 'pil': pil})

        pairs = []

        for gt_idx, gt_path in gt_list:
            gt_cv = load_image_cv(gt_path)
            gt_proc = preprocess_for_features(gt_cv)
            kp1, des1 = detector.detectAndCompute(gt_proc, None)
            gt_pil = cv_to_pil(gt_cv)
            gt_ph = compute_phash_pil(gt_pil) if USE_PHASH else None

            for mp in mp_db:
                good = match_descriptors(matcher, des1, mp['des'], descriptor_type)
                num_good = len(good)
                match_info = compute_match_score(kp1, mp['kp'], good)
                inliers = match_info['inliers']
                ratio = (inliers / num_good) if num_good else 0

                ph_dist = None
                if USE_PHASH and gt_ph and mp['phash']:
                    ph_dist = gt_ph - mp['phash']

                score = {
                    'gt_path': gt_path,
                    'gt_pil': gt_pil,
                    'mp_path': mp['path'],
                    'mp_pil': mp['pil'],
                    'inliers': inliers,
                    'good_matches': num_good,
                    'inlier_ratio': ratio,
                    'phash_dist': ph_dist
                }

                pairs.append((gt_idx, mp['idx'], score))

        # --------------------------------------------------------
        # STEP 2 — Sort candidate pairs globally (best first)
        # --------------------------------------------------------
        def pair_sort_key(x):
            _, _, s = x
            return (
                -s['inliers'],
                -s['inlier_ratio'],
                s['phash_dist'] if s['phash_dist'] is not None else 999
            )

        pairs.sort(key=pair_sort_key)

        # --------------------------------------------------------
        # STEP 3 — Greedy one-to-one assignment
        # --------------------------------------------------------
        used_gt = set()
        used_mp = set()
        assignments = {}     # gt_idx → score_dict

        for gt_idx, mp_idx, s in pairs:
            if gt_idx in used_gt:
                continue
            if mp_idx in used_mp:
                continue

            used_gt.add(gt_idx)
            used_mp.add(mp_idx)
            assignments[gt_idx] = s

        # --------------------------------------------------------
        # STEP 4 — Produce final results per GT (with acceptance logic)
        # --------------------------------------------------------
        for gt_idx, gt_path in gt_list:
            progress += 1

            if gt_idx not in assignments:
                # GT was unmatched (all MPs taken or no good candidates)
                results.append({
                    'gt_path': gt_path,
                    'gt_pil': cv_to_pil(load_image_cv(gt_path)),
                    'mp_path': None,
                    'mp_pil': None,
                    'inliers': 0,
                    'good_matches': 0,
                    'inlier_ratio': 0,
                    'phash_dist': None,
                    'accepted': False,
                    'reason': "No assignment candidate"
                })

                print(
                    f"[{progress}/{total_gt}] Page {page} GT:{os.path.basename(gt_path)} → --- | no assignment"
                )
                continue

            # Assigned match:
            s = assignments[gt_idx]

            # Apply your original acceptance rules:
            if s['inliers'] >= MIN_INLIERS and s['inlier_ratio'] >= MIN_INLIER_RATIO:
                accepted = True
                reason = "Strong geometric match (SIFT+RANSAC)"
                # used_gt.add(gt_idx)
                # used_mp.add(mp_idx)
            elif USE_PHASH and s['phash_dist'] is not None and s['phash_dist'] <= PHASH_DIST_THRESHOLD:
                accepted = True
                reason = f"phash match ({s['phash_dist']})"
                # used_gt.add(gt_idx)
                # used_mp.add(mp_idx)
            else:
                accepted = False
                reason = "Nearest candidate does not meet thresholds"

            results.append({
                'gt_path': s['gt_path'],
                'gt_pil': s['gt_pil'],
                'mp_path': s['mp_path'],
                'mp_pil': s['mp_pil'],
                'inliers': s['inliers'],
                'good_matches': s['good_matches'],
                'inlier_ratio': s['inlier_ratio'],
                'phash_dist': s['phash_dist'],
                'accepted': accepted,
                'reason': reason
            })

            print(
                f"[{progress}/{total_gt}] Page {page} GT:{os.path.basename(s['gt_path'])} → "
                f"{os.path.basename(s['mp_path'])} | inliers={s['inliers']} accepted={accepted}"
            )



  
    # Write CSV
    with open(csv_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['gt_path','mp_path','inliers','good_matches','inlier_ratio','phash_dist','accepted','reason'])
        for r in results:
            writer.writerow([r['gt_path'], r['mp_path'] or '', r['inliers'], r['good_matches'], f"{r['inlier_ratio']:.3f}", r['phash_dist'] if r['phash_dist'] is not None else '', r['accepted'], r['reason']])

    # Generate HTML report
    generate_html_report(results, html_out)
    print("Done. HTML report:", html_out, "CSV:", csv_out)


import re

def add_image(image_path, tex_file, book_len):
    # get page number from image
    page, _ = parse_gt_name(image_path)

    # find page breaks
    page_break_pattern = r'%---- Page End Break Here ---- Page : (\d+)'
    page_breaks = re.findall(page_break_pattern, tex_file)
    page_positions = {
        int(p): m.start()
        for p, m in zip(
            page_breaks,
            re.finditer(page_break_pattern, tex_file)
        )
    }

    # determine insertion bounds
    upper_bound = find_closest_page(
        page + 1, page_breaks, page_positions, book_len, True
    )
    lower_bound = find_closest_page(
        page - 2, page_breaks, page_positions, False
    )

    # clamp bounds safely
    start = lower_bound if lower_bound is not None else 0
    end = upper_bound if upper_bound is not None else len(tex_file)

    # find first newline within bounds
    newline_idx = tex_file.find('\n', start, end)
    if newline_idx == -1:
        return tex_file  # no safe insertion point

    # latex image block
    image_block = (
        "\n\\begin{figure}[htbp]\n"
        "    \\centering\n"
        f"    \\includegraphics[width=\\linewidth]{{{image_path}}}\n"
        "\\end{figure}\n"
    )

    # insert image
    tex_file = (
        tex_file[:newline_idx + 1]
        + image_block
        + tex_file[newline_idx + 1:]
    )

    return tex_file

import os
import shutil

def add_image_from_gt_to_mp(gt_path, mp_folder, overwrite=True):
    """
    Copy image from gt_path into mp_folder, keeping original filename.
    """

    if not os.path.isfile(gt_path):
        raise FileNotFoundError(f"GT image not found: {gt_path}")

    if not os.path.isdir(mp_folder):
        os.makedirs(mp_folder, exist_ok=True)

    filename = os.path.basename(gt_path)
    dest_path = os.path.join(mp_folder, filename)

    if os.path.exists(dest_path) and not overwrite:
        return dest_path  # already exists, skipped

    shutil.copy2(gt_path, dest_path)
    return dest_path



import pymupdf

def add_images_to_tex(gt_folder, mp_folder, tex_file, pdf_path):

    # get book length from pdf
    content_book_pdf = pymupdf.open(pdf_path)
    book_len = len(content_book_pdf)
    print("CHECK HERE HERE")
    print(f"GT FOLDER IS: {gt_folder}")

    gt_folder =  gt_folder+ "/images"
    print(f"GT UPDATED FOLDER IS: {gt_folder}")

    gt_images = list_images(gt_folder)
    mp_images = list_images(mp_folder)

    # Group images by page
    gt_pages = group_by_page(gt_images, parse_gt_name)
    mp_pages = group_by_page(mp_images, parse_mathpix_name)

    if len(gt_images) == 0:
        print("No GT images found in", gt_folder)
        return
    if len(mp_images) == 0:
        print("No Mathpix images found in", mp_folder)
        return

    detector, matcher, descriptor_type = init_feature_detector()
    print(f"Using descriptor: {descriptor_type}")

    # Precompute images, descriptors, keypoints, phash
    mp_db = []
    print("Preprocessing Mathpix images...")
    for i, mp_path in enumerate(mp_images):
        if MAX_COMPARE and i >= MAX_COMPARE:
            break
        img_cv = load_image_cv(mp_path)
        proc = preprocess_for_features(img_cv)
        kp, des = detector.detectAndCompute(proc, None)
        pil = cv_to_pil(img_cv)
        ph = compute_phash_pil(pil) if USE_PHASH else None
        mp_db.append({'path': mp_path, 'cv': img_cv, 'proc': proc, 'kp': kp, 'des': des, 'phash': ph, 'pil': pil})

    results = []
    total_gt = sum(len(v) for v in gt_pages.values())
    progress = 0
    print("Comparing GT images (page-constrained)...")

    for page in sorted(gt_pages.keys()):
        gt_list = gt_pages[page]
        mp_list = mp_pages.get(page, [])

         # If counts match → assume correct and skip
        # if len(gt_list) == len(mp_list):
        #     for idx, gt_path in gt_list:
        #         results.append({
        #             'gt_path': gt_path,
        #             'gt_pil': cv_to_pil(load_image_cv(gt_path)),
        #             'mp_path': None,
        #             'mp_pil': None,
        #             'inliers': 0,
        #             'good_matches': 0,
        #             'inlier_ratio': 0,
        #             'phash_dist': None,
        #             'accepted': True,
        #             'reason': 'Count match → assumed correct'
        #         })
        #     continue

        # Otherwise: perform local matching only within this page
        print(f"Page {page}: GT={len(gt_list)}, MP={len(mp_list)} → comparing...")
        
        # Precompute MP page descriptors
        mp_db = []
        for idx, mp_path in mp_list:
            img_cv = load_image_cv(mp_path)
            proc = preprocess_for_features(img_cv)
            kp, des = detector.detectAndCompute(proc, None)
            pil = cv_to_pil(img_cv)
            ph = compute_phash_pil(pil) if USE_PHASH else None
            mp_db.append({'idx':idx, 'path': mp_path, 'kp': kp, 'des': des, 'phash': ph, 'pil': pil})

        pairs = []

        for gt_idx, gt_path in gt_list:
            gt_cv = load_image_cv(gt_path)
            gt_proc = preprocess_for_features(gt_cv)
            kp1, des1 = detector.detectAndCompute(gt_proc, None)
            gt_pil = cv_to_pil(gt_cv)
            gt_ph = compute_phash_pil(gt_pil) if USE_PHASH else None

            for mp in mp_db:
                good = match_descriptors(matcher, des1, mp['des'], descriptor_type)
                num_good = len(good)
                match_info = compute_match_score(kp1, mp['kp'], good)
                inliers = match_info['inliers']
                ratio = (inliers / num_good) if num_good else 0

                ph_dist = None
                if USE_PHASH and gt_ph and mp['phash']:
                    ph_dist = gt_ph - mp['phash']

                score = {
                    'gt_path': gt_path,
                    'gt_pil': gt_pil,
                    'mp_path': mp['path'],
                    'mp_pil': mp['pil'],
                    'inliers': inliers,
                    'good_matches': num_good,
                    'inlier_ratio': ratio,
                    'phash_dist': ph_dist
                }

                pairs.append((gt_idx, mp['idx'], score))

        # --------------------------------------------------------
        # STEP 2 — Sort candidate pairs globally (best first)
        # --------------------------------------------------------
        def pair_sort_key(x):
            _, _, s = x
            return (
                -s['inliers'],
                -s['inlier_ratio'],
                s['phash_dist'] if s['phash_dist'] is not None else 999
            )

        pairs.sort(key=pair_sort_key)

        # --------------------------------------------------------
        # STEP 3 — Greedy one-to-one assignment
        # --------------------------------------------------------
        used_gt = set()
        used_mp = set()
        assignments = {}     # gt_idx → score_dict

        for gt_idx, mp_idx, s in pairs:
            if gt_idx in used_gt:
                continue
            if mp_idx in used_mp:
                continue

            used_gt.add(gt_idx)
            used_mp.add(mp_idx)
            assignments[gt_idx] = s

        # --------------------------------------------------------
        # STEP 4 — Produce final results per GT (with acceptance logic)
        # --------------------------------------------------------
        for gt_idx, gt_path in gt_list:
            progress += 1

            if gt_idx not in assignments:
                # GT was unmatched (all MPs taken or no good candidates)
                results.append({
                    'gt_path': gt_path,
                    'gt_pil': cv_to_pil(load_image_cv(gt_path)),
                    'mp_path': None,
                    'mp_pil': None,
                    'inliers': 0,
                    'good_matches': 0,
                    'inlier_ratio': 0,
                    'phash_dist': None,
                    'accepted': False,
                    'reason': "No assignment candidate"
                })

                # add gt image to mp folder
                new_path = add_image_from_gt_to_mp(gt_path, mp_folder, overwrite=True)
                # just take the last folder and filename as new path
                #  os.path.join(os.path.basename(mp_folder),
                new_path = os.path.basename(new_path)
                print(f"NEW PATH IS: {new_path}")
                tex_file = add_image(new_path, tex_file, book_len)

                print(
                    f"[{progress}/{total_gt}] Page {page} GT:{os.path.basename(gt_path)} → --- | no assignment"
                )
                continue

            # Assigned match:
            s = assignments[gt_idx]

            # Apply your original acceptance rules:
            if s['inliers'] >= MIN_INLIERS and s['inlier_ratio'] >= MIN_INLIER_RATIO:
                accepted = True
                reason = "Strong geometric match (SIFT+RANSAC)"
                # used_gt.add(gt_idx)
                # used_mp.add(mp_idx)
            elif USE_PHASH and s['phash_dist'] is not None and s['phash_dist'] <= PHASH_DIST_THRESHOLD:
                accepted = True
                reason = f"phash match ({s['phash_dist']})"
                # used_gt.add(gt_idx)
                # used_mp.add(mp_idx)
            else:
                accepted = False
                reason = "Nearest candidate does not meet thresholds"

            results.append({
                'gt_path': s['gt_path'],
                'gt_pil': s['gt_pil'],
                'mp_path': s['mp_path'],
                'mp_pil': s['mp_pil'],
                'inliers': s['inliers'],
                'good_matches': s['good_matches'],
                'inlier_ratio': s['inlier_ratio'],
                'phash_dist': s['phash_dist'],
                'accepted': accepted,
                'reason': reason
            })

            if not accepted:
                # add gt image to mp folder
                new_path = add_image_from_gt_to_mp(s['gt_path'], mp_folder, overwrite=True)
                # just take the last folder and filename as new path
                new_path = os.path.join(os.path.basename(mp_folder), os.path.basename(new_path))
                print(f"NEW PATH IS: {new_path}")
                tex_file = add_image(new_path, tex_file, book_len)

            print(
                f"[{progress}/{total_gt}] Page {page} GT:{os.path.basename(s['gt_path'])} → "
                f"{os.path.basename(s['mp_path'])} | inliers={s['inliers']} accepted={accepted}"
            )

    return tex_file

  
    # # Write CSV
    # with open(csv_out, 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['gt_path','mp_path','inliers','good_matches','inlier_ratio','phash_dist','accepted','reason'])
    #     for r in results:
    #         writer.writerow([r['gt_path'], r['mp_path'] or '', r['inliers'], r['good_matches'], f"{r['inlier_ratio']:.3f}", r['phash_dist'] if r['phash_dist'] is not None else '', r['accepted'], r['reason']])

    # # Generate HTML report
    # generate_html_report(results, html_out)
    # print("Done. HTML report:", html_out, "CSV:", csv_out)




def generate_html_report(results, outpath):
    ts = datetime.now().isoformat(sep=' ', timespec='seconds')
    html_parts = []
    html_parts.append(f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Image Compare Report</title>
<style>
body {{ font-family: Arial, sans-serif; padding: 16px; }}
.header {{ display:flex; align-items:center; justify-content:space-between; }}
.card {{ border: 1px solid #ddd; border-radius:6px; padding:10px; margin:10px 0; display:flex; gap:12px; align-items:flex-start; }}
.thumb {{ width: {THUMB_W}px; border:1px solid #ccc; }}
.meta {{ flex:1; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:4px; font-weight:600; }}
.accept {{ background:#daf5d8; color:#1b5e20; }}
.reject {{ background:#ffdede; color:#8b0000; }}
.controls {{ margin: 10px 0; }}
.unmatched {{ border-color: #ff9b9b; }}
table.report {{ border-collapse: collapse; width: 100%; }}
table.report td, table.report th {{ padding: 6px; border-bottom: 1px solid #eee; vertical-align: top; }}
small.note {{ color:#666; }}
.filter-note {{ font-size:0.95em; color:#333; }}
</style>
</head>
<body>
<div class="header">
  <div><h2>Image Compare Report</h2><div class="filter-note">Generated: {ts}</div></div>
  <div><small class="note">Show only unmatched: <input id="showUnmatched" type="checkbox" onchange="toggleUnmatched()"></small></div>
</div>
<div class="controls">
  <small>Legend: <span class="badge accept">Accepted Match</span> <span class="badge reject">No Match / Candidate</span></small>
</div>
<div id="results">
""")

    # Each result card
    for i, r in enumerate(results):
        gt_name = os.path.basename(r['gt_path'])
        mp_name = os.path.basename(r['mp_path']) if r['mp_path'] else '---'
        accepted = r['accepted']
        cls = '' if accepted else 'unmatched'
        status_badge = '<span class="badge accept">Match</span>' if accepted else '<span class="badge reject">No Match</span>'
        phash_txt = f"{r['phash_dist']}" if r['phash_dist'] is not None else 'N/A'
        # images to data URIs
        gt_data = pil_to_data_uri(r['gt_pil'], fmt='PNG', max_width=THUMB_W)
        mp_data = pil_to_data_uri(r['mp_pil'], fmt='PNG', max_width=THUMB_W) if r['mp_pil'] else ''

        html_parts.append(f"""
<div class="card {cls}" data-accepted="{str(accepted).lower()}">
  <div style="min-width:{THUMB_W}px;">
    <div><img class="thumb" src="{gt_data}" alt="GT image"></div>
    <div style="text-align:center; margin-top:6px;"><small>GT: {gt_name}</small></div>
  </div>
  <div class="meta">
    <div style="margin-bottom:8px;">{status_badge} <strong>{mp_name}</strong> &nbsp; <small class="note"> (reason: {r['reason']})</small></div>
    <table class="report">
      <tr><th style="width:160px">Metric</th><th>Value</th></tr>
      <tr><td>Inliers</td><td>{r['inliers']}</td></tr>
      <tr><td>Good matches</td><td>{r['good_matches']}</td></tr>
      <tr><td>Inlier ratio</td><td>{r['inlier_ratio']:.3f}</td></tr>
      <tr><td>pHash distance</td><td>{phash_txt}</td></tr>
    </table>
    <div style="margin-top:10px;">
      <strong>Candidate:</strong>
      <div style="margin-top:6px;">
        {"<img class='thumb' src='" + mp_data + "' alt='MP image'>" if mp_data else "<small class='note'>No candidate found</small>"}
      </div>
    </div>
  </div>
</div>
""")

    # Footer with JS toggle
    html_parts.append("""
</div> <!-- results -->
<script>
function toggleUnmatched(){
  const showOnly = document.getElementById('showUnmatched').checked;
  const cards = document.querySelectorAll('.card');
  cards.forEach(c => {
    const accepted = c.getAttribute('data-accepted') === 'true';
    if(showOnly){
      // show only unmatched (accepted === false)
      if(accepted) c.style.display = 'none';
      else c.style.display = 'flex';
    } else {
      c.style.display = 'flex';
    }
  });
}
// init (unchecked)
toggleUnmatched();
</script>
</body>
</html>
""")

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(''.join(html_parts))


# ---------------------------
# CLI
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="Compare GT images vs Mathpix images and generate HTML report.")
    parser.add_argument('--gt_folder', help='Folder with ground-truth images')
    parser.add_argument('--mp_folder', help='Folder with Mathpix-extracted images')
    parser.add_argument('--out', '-o', default='compare_report.html', help='HTML output path')
    parser.add_argument('--csv', default='compare_report.csv', help='CSV output path')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of images processed (for testing)')
    args = parser.parse_args()

    global MAX_COMPARE
    if args.limit and args.limit > 0:
        MAX_COMPARE = args.limit

    compare_folders(args.gt_folder, args.mp_folder, html_out=args.out, csv_out=args.csv)

if __name__ == '__main__':
    main()
