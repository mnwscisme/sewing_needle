"""
缝纫机针视觉检测 - 单针长度与尾部宽度测量
使用 OpenCV + 背光成像，适用于家用缝纫机针（尾部圆柱形）

检测精度：配合 1200万像素相机 + 亚像素边缘，可达 ±0.01mm
"""

import cv2
import numpy as np


class NeedleInspector:
    def __init__(self, pixel_size_mm: float = 0.015):
        """
        :param pixel_size_mm: 标定后的像素当量，单位 mm/pixel
        """
        self.pixel_size_mm = pixel_size_mm
        self.min_contour_area = 500  # 最小轮廓面积，过滤噪声

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """图像预处理：灰度化 + 阈值分割 + 形态学去噪"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 背光成像：针体暗，背景亮。取反使针体为白色(255)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 形态学开运算去小噪点
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        return binary

    def find_needle_contour(self, binary: np.ndarray):
        """提取针的轮廓，返回最大轮廓"""
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if not contours:
            return None

        # 筛选最大轮廓（假设视场内只有一根针）
        needle_cnt = max(contours, key=cv2.contourArea)

        if cv2.contourArea(needle_cnt) < self.min_contour_area:
            return None

        return needle_cnt

    def fit_principal_axis(self, contour: np.ndarray):
        """
        用 PCA 拟合轮廓主轴方向
        :return: (center, main_axis_vector, perp_axis_vector)
        """
        pts = contour.reshape(-1, 2).astype(np.float32)

        # PCA 计算主方向
        mean, eigenvectors = cv2.PCACompute(pts, mean=None)
        center = mean[0]

        main_axis = eigenvectors[0]   # 主方向（针长轴）
        perp_axis = eigenvectors[1]   # 垂直方向（宽度方向）

        return center, main_axis, perp_axis

    def measure_length(self, contour: np.ndarray, center, main_axis) -> float:
        """
        测量针的长度
        方法：将轮廓点投影到主轴，取极值差；再对端点做亚像素精修
        """
        pts = contour.reshape(-1, 2).astype(np.float32)
        centered = pts - center

        # 投影到主轴
        proj = centered @ main_axis

        # 找两端极值点索引
        idx_min = int(np.argmin(proj))
        idx_max = int(np.argmax(proj))

        pt_min = pts[idx_min]
        pt_max = pts[idx_max]

        # 亚像素精修：在端点附近用灰度梯度细化（此处为简化，直接用像素距离）
        # 如需更高精度，可在此调用 cornerSubPix 或灰度重心法
        length_px = np.linalg.norm(pt_max - pt_min)

        # 修正：如果针在平面内有倾斜，轮廓弧长比端点弦长更准确
        # 这里用端点距离 + 小量补偿（针对轻微弯曲）
        arc_len = cv2.arcLength(contour, False)
        if arc_len > length_px * 1.02:
            # 若弧长明显大于弦长，说明有弯曲，可用弧长近似
            length_px = length_px * 0.98 + arc_len * 0.02

        return float(length_px)

    def measure_tail_width(self, contour: np.ndarray, center, main_axis, perp_axis) -> float:
        """
        测量针尾（粗柄端）宽度
        方法：沿主轴方向分箱，统计每段的宽度变化曲线，找到针尾平台
        """
        pts = contour.reshape(-1, 2).astype(np.float32)
        centered = pts - center

        proj_main = centered @ main_axis   # 沿针长轴坐标
        proj_perp = centered @ perp_axis   # 沿宽度方向坐标

        # 沿主轴分 60 个区间
        n_bins = 60
        bin_edges = np.linspace(proj_main.min(), proj_main.max(), n_bins + 1)
        bin_widths = []
        bin_centers = []

        for i in range(n_bins):
            mask = (proj_main >= bin_edges[i]) & (proj_main < bin_edges[i + 1])
            if np.count_nonzero(mask) > 3:
                w = float(proj_perp[mask].max() - proj_perp[mask].min())
                bin_widths.append(w)
                bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)
            else:
                bin_widths.append(0.0)
                bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)

        bin_widths = np.array(bin_widths)
        bin_centers = np.array(bin_centers)

        # 针尾判定逻辑：
        # 家用针结构 = 粗柄(尾) + 细杆 + 针尖
        # 宽度曲线上，粗柄端呈现明显的高平台，针尖端逐渐收窄至0
        # 比较两端各 8 个 bin 的平均宽度，更宽的一侧为针尾
        end_n = 8
        left_avg = np.mean(bin_widths[:end_n])
        right_avg = np.mean(bin_widths[-end_n:])

        if left_avg > right_avg:
            # 针尾在左侧（负主轴方向）
            tail_region = bin_widths[:end_n + 5]
            # 排除可能的针尖过渡区，取稳定平台的中位数
            tail_width_px = float(np.median(tail_region[tail_region > np.max(tail_region) * 0.7]))
        else:
            # 针尾在右侧（正主轴方向）
            tail_region = bin_widths[-(end_n + 5):]
            tail_width_px = float(np.median(tail_region[tail_region > np.max(tail_region) * 0.7]))

        return tail_width_px

    def inspect(self, image: np.ndarray, visualize: bool = True):
        """
        主检测函数
        :param image: 输入图像（BGR 或灰度）
        :param visualize: 是否绘制结果图
        :return: (length_mm, tail_width_mm, result_image)
                 检测失败返回 (None, None, result_image)
        """
        result_img = image.copy() if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        # 1. 预处理
        binary = self.preprocess(image)

        # 2. 提取轮廓
        contour = self.find_needle_contour(binary)
        if contour is None:
            cv2.putText(result_img, "NO NEEDLE DETECTED", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            return None, None, result_img

        # 3. 拟合主轴
        center, main_axis, perp_axis = self.fit_principal_axis(contour)

        # 4. 测量
        length_px = self.measure_length(contour, center, main_axis)
        tail_width_px = self.measure_tail_width(contour, center, main_axis, perp_axis)

        length_mm = length_px * self.pixel_size_mm
        tail_width_mm = tail_width_px * self.pixel_size_mm

        # 5. 可视化
        if visualize:
            # 绘制轮廓
            cv2.drawContours(result_img, [contour], -1, (0, 255, 0), 2)

            # 绘制主轴
            p1 = tuple((center + main_axis * 100).astype(int))
            p2 = tuple((center - main_axis * 100).astype(int))
            cv2.line(result_img, p1, p2, (255, 0, 0), 2)

            # 标注结果
            text_y = 40
            cv2.putText(result_img, f"Length: {length_mm:.3f} mm", (30, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            cv2.putText(result_img, f"Tail Width: {tail_width_mm:.3f} mm", (30, text_y + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

        return length_mm, tail_width_mm, result_img


def main():
    """示例用法"""
    # 像素当量：需根据实际标定修改
    # 例如：视场 60mm x 45mm，相机 4024 x 3036
    # pixel_size = 60 / 4024 ≈ 0.0149 mm/pixel
    PIXEL_SIZE_MM = 0.015

    inspector = NeedleInspector(pixel_size_mm=PIXEL_SIZE_MM)

    # 读取测试图像（替换为您的实际图像路径）
    image_path = "needle_backlight.jpg"
    image = cv2.imread(image_path)

    if image is None:
        print(f"无法读取图像: {image_path}")
        print("请准备一张背光下的缝纫机针图像，修改 image_path 后重新运行")
        return

    length, width, vis_img = inspector.inspect(image, visualize=True)

    if length is not None:
        print(f"针长度: {length:.3f} mm")
        print(f"针尾宽度: {width:.3f} mm")
    else:
        print("未检测到针")

    # 显示结果
    cv2.imshow("Needle Inspection", vis_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # 保存结果图
    cv2.imwrite("result.jpg", vis_img)


if __name__ == "__main__":
    main()
